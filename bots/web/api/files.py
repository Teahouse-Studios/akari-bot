from __future__ import annotations

import hashlib
import pkgutil
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from bots.web.client import app, get_client_ip, limiter
from core.constants.path import assets_path, cache_path, data_path, modules_path
from core.logger import Logger
from .auth import verify_jwt

ROOT_DIR = Path(__file__).parent.parent.parent.parent.resolve()

MAX_PATH_LENGTH = 256
MAX_NAME_LENGTH = 255
MAX_CONTENT_BYTES = 1024 * 1024
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
REVISION_LENGTH = 16


def _revision_of(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:REVISION_LENGTH]


def _module_names() -> list[str]:
    import modules

    names = []
    for info in pkgutil.iter_modules(modules.__path__):
        if info.name.startswith(("_", ".")):
            continue
        if (modules_path / info.name).is_dir():
            names.append(info.name)
    return sorted(names)


def _root_paths() -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for target, path in (("assets", assets_path), ("data", data_path), ("cache", cache_path)):
        if path.is_dir():
            roots[f"core:{target}"] = path
    for name in _module_names():
        module_path = modules_path / name
        for target in ("assets", "data"):
            path = module_path / target
            if path.is_dir():
                roots[f"module:{name}:{target}"] = path
    return roots


def _resolve_root(root_id: str) -> Path:
    root = _root_paths().get(root_id)
    if root is None:
        raise HTTPException(status_code=404, detail="unknown_root")
    return root.resolve()


def _resolve_path(root: Path, relative: str) -> Path:
    relative = relative.replace("\\", "/")
    if len(relative) > MAX_PATH_LENGTH:
        raise HTTPException(status_code=403, detail="path_too_long")
    try:
        target = (root / relative).resolve()
        target.relative_to(root)
    except (OSError, ValueError):
        raise HTTPException(status_code=403, detail="forbidden_path") from None
    return target


def _display_path(path: Path) -> str:
    try:
        return f"./{path.resolve().relative_to(ROOT_DIR).as_posix()}"
    except (OSError, ValueError):
        return str(path)


def _relative_path(target: Path, root: Path) -> str:
    relative = target.relative_to(root).as_posix()
    return "" if relative == "." else relative


def _file_revision(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return _revision_of(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")


def _assert_revision(expected, current: str | None) -> None:
    if expected is None or expected == "":
        return
    if not isinstance(expected, str):
        raise HTTPException(status_code=400, detail="invalid_body")
    if expected != current:
        headers = {"X-Storage-Revision": current} if current else None
        raise HTTPException(status_code=409, detail="revision_mismatch", headers=headers)


def _file_info(path: Path, root: Path) -> dict | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    is_dir = path.is_dir()
    return {
        "name": path.name,
        "path": _relative_path(path, root),
        "is_dir": is_dir,
        "size": 0 if is_dir else stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "revision": None if is_dir else _revision_of(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}"),
    }


def _dump_root(root_id: str, path: Path) -> dict:
    if root_id.startswith("core:"):
        scope, module, target = "core", None, root_id.split(":", 1)[1]
    else:
        _, module, target = root_id.split(":", 2)
        scope = "module"
    return {
        "id": root_id,
        "scope": scope,
        "module": module,
        "target": target,
        "path": _display_path(path),
        "exists": path.is_dir(),
    }


def _validate_name(name: str) -> str:
    if (
        not isinstance(name, str)
        or not name
        or name in (".", "..")
        or len(name) > MAX_NAME_LENGTH
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise HTTPException(status_code=422, detail="invalid_name")
    return name


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid_body")
    return body


def _body_root_and_path(body: dict) -> tuple[str, str]:
    root_id = body.get("root")
    relative = body.get("path", "")
    if not isinstance(root_id, str) or not isinstance(relative, str):
        raise HTTPException(status_code=400, detail="invalid_body")
    return root_id, relative


def _list_entries(root_id: str, relative: str) -> dict:
    root_path = _resolve_root(root_id)
    target = _resolve_path(root_path, relative)
    if target.exists() and not target.is_dir():
        raise HTTPException(status_code=400, detail="not_a_directory")
    if not target.exists():
        return {"root": root_id, "path": _relative_path(target, root_path), "exists": False, "files": []}

    files = [
        info
        for entry in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        if (info := _file_info(entry, root_path)) is not None
    ]
    return {"root": root_id, "path": _relative_path(target, root_path), "exists": True, "files": files}


def _download_entry(root_id: str, relative: str, inline: bool, ip: str) -> FileResponse:
    root_path = _resolve_root(root_id)
    target = _resolve_path(root_path, relative)
    if not target.exists():
        raise HTTPException(status_code=404, detail="not_found")

    if target.is_file():
        Logger.info(f'[WebUI] {ip} downloaded storage file: "{root_id}:{_relative_path(target, root_path)}"')
        return FileResponse(
            target,
            filename=target.name,
            content_disposition_type="inline" if inline else "attachment",
        )

    temp_dir = tempfile.mkdtemp()
    zip_name = f"{target.name or 'root'}.zip"
    zip_path = Path(temp_dir) / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file in target.rglob("*"):
            if not file.is_file() or file.is_symlink():
                continue
            try:
                file.resolve().relative_to(root_path)
            except (OSError, ValueError):
                continue
            zip_file.write(file, file.relative_to(target))
    Logger.info(f'[WebUI] {ip} downloaded storage directory: "{root_id}:{_relative_path(target, root_path)}"')
    return FileResponse(zip_path, filename=zip_name, background=BackgroundTask(shutil.rmtree, temp_dir))


def _read_entry(root_id: str, relative: str) -> dict:
    root_path = _resolve_root(root_id)
    target = _resolve_path(root_path, relative)
    if target.is_dir():
        raise HTTPException(status_code=400, detail="is_directory")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="not_found")

    stat = target.stat()
    if stat.st_size > MAX_CONTENT_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="not_text") from None

    return {
        "root": root_id,
        "path": _relative_path(target, root_path),
        "content": content,
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "revision": _revision_of(f"{target.name}:{stat.st_mtime_ns}:{stat.st_size}"),
    }


def _write_entry(root_id: str, relative: str, content: str, revision, ip: str) -> dict:
    root_path = _resolve_root(root_id)
    target = _resolve_path(root_path, relative)
    if _relative_path(target, root_path) == "":
        raise HTTPException(status_code=400, detail="invalid_path")
    if target.exists() and target.is_dir():
        raise HTTPException(status_code=400, detail="is_directory")

    encoded = content.encode("utf-8")
    if len(encoded) > MAX_CONTENT_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")

    _assert_revision(revision, _file_revision(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded)
    Logger.info(f'[WebUI] {ip} wrote storage file: "{root_id}:{_relative_path(target, root_path)}"')
    return {
        "changed": True,
        "root": root_id,
        "entry": _file_info(target, root_path),
    }


def _upload_entry(root_id: str, relative: str, filename: str, content: bytes, ip: str) -> dict:
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    _validate_name(filename)

    root_path = _resolve_root(root_id)
    target_dir = _resolve_path(root_path, relative)
    if target_dir.exists() and not target_dir.is_dir():
        raise HTTPException(status_code=400, detail="not_a_directory")

    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    if target.is_symlink():
        raise HTTPException(status_code=403, detail="forbidden_path")
    if target.is_dir():
        raise HTTPException(status_code=400, detail="is_directory")
    target.write_bytes(content)
    Logger.info(f'[WebUI] {ip} uploaded storage file: "{root_id}:{_relative_path(target, root_path)}"')
    return {
        "changed": True,
        "root": root_id,
        "entry": _file_info(target, root_path),
    }


def _create_entry(root_id: str, relative: str, name: str, entry_type: str, ip: str) -> dict:
    name = _validate_name(name)
    root_path = _resolve_root(root_id)
    parent = _resolve_path(root_path, relative)
    if parent.exists() and not parent.is_dir():
        raise HTTPException(status_code=400, detail="not_a_directory")

    target = parent / name
    if target.exists() or target.is_symlink():
        raise HTTPException(status_code=409, detail="already_exists")

    parent.mkdir(parents=True, exist_ok=True)
    if entry_type == "dir":
        target.mkdir()
    else:
        target.touch()
    Logger.info(f'[WebUI] {ip} created storage {entry_type}: "{root_id}:{_relative_path(target, root_path)}"')
    return {
        "changed": True,
        "root": root_id,
        "entry": _file_info(target, root_path),
    }


def _rename_entry(root_id: str, relative: str, new_name: str, ip: str) -> dict:
    new_name = _validate_name(new_name)
    root_path = _resolve_root(root_id)
    source = _resolve_path(root_path, relative)
    if _relative_path(source, root_path) == "":
        raise HTTPException(status_code=403, detail="cannot_modify_root")
    if not source.exists() and not source.is_symlink():
        raise HTTPException(status_code=404, detail="not_found")

    target = source.parent / new_name
    if source.is_dir():
        try:
            target.relative_to(source)
        except ValueError:
            pass
        else:
            raise HTTPException(status_code=400, detail="cannot_move_into_itself")
    if target.exists() or target.is_symlink():
        raise HTTPException(status_code=409, detail="already_exists")

    source.rename(target)
    Logger.info(
        f'[WebUI] {ip} renamed storage entry: "{root_id}:{_relative_path(source, root_path)}" '
        f'-> "{root_id}:{_relative_path(target, root_path)}"'
    )
    return {
        "changed": True,
        "root": root_id,
        "entry": _file_info(target, root_path),
    }


def _delete_entry(root_id: str, relative: str, revision, ip: str) -> None:
    root_path = _resolve_root(root_id)
    target = _resolve_path(root_path, relative)
    if _relative_path(target, root_path) == "":
        raise HTTPException(status_code=403, detail="cannot_modify_root")
    if not target.exists() and not target.is_symlink():
        raise HTTPException(status_code=404, detail="not_found")

    if target.is_file() or target.is_symlink():
        _assert_revision(revision, _file_revision(target))
        target.unlink()
    else:
        shutil.rmtree(target)
    Logger.info(f'[WebUI] {ip} deleted storage entry: "{root_id}:{_relative_path(target, root_path)}"')


@app.get("/api/files/roots")
@limiter.limit("60/minute")
async def get_storage_roots(request: Request):
    try:
        verify_jwt(request)

        return {"roots": [_dump_root(root_id, path) for root_id, path in _root_paths().items()]}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/files/list")
@limiter.limit("60/minute")
async def list_storage(request: Request, root: str = Query(...), path: str = ""):
    try:
        verify_jwt(request)

        return _list_entries(root, path)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/files/download")
@limiter.limit("20/minute")
def download_storage(request: Request, root: str = Query(...), path: str = "", inline: bool = False):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        return _download_entry(root, path, inline, ip)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/files/content")
@limiter.limit("60/minute")
async def read_storage_content(request: Request, root: str = Query(...), path: str = Query(...)):
    try:
        verify_jwt(request)

        return _read_entry(root, path)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.put("/api/files/content")
@limiter.limit("30/minute")
async def write_storage_content(request: Request):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        body = await _json_body(request)
        content = body.get("content")
        if not isinstance(content, str):
            raise HTTPException(status_code=400, detail="invalid_body")

        root_id, relative = _body_root_and_path(body)
        return _write_entry(root_id, relative, content, body.get("revision"), ip)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/files/upload")
@limiter.limit("20/minute")
async def upload_storage_file(
    request: Request,
    root: str = Form(...),
    path: str = Form(""),
    file: UploadFile = File(...),
):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="file_too_large")

        return _upload_entry(root, path, file.filename or "", content, ip)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/files/create")
@limiter.limit("20/minute")
async def create_storage_entry(request: Request):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        body = await _json_body(request)
        entry_type = body.get("type", "file")
        if entry_type not in ("file", "dir"):
            raise HTTPException(status_code=400, detail="invalid_type")

        root_id, relative = _body_root_and_path(body)
        return _create_entry(root_id, relative, body.get("name"), entry_type, ip)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/files/rename")
@limiter.limit("20/minute")
async def rename_storage_entry(request: Request):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        body = await _json_body(request)
        root_id, relative = _body_root_and_path(body)
        return _rename_entry(root_id, relative, body.get("new_name"), ip)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.delete("/api/files/entry")
@limiter.limit("20/minute")
async def delete_storage_entry(
    request: Request,
    root: str = Query(...),
    path: str = Query(...),
    revision: str | None = None,
):
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        _delete_entry(root, path, revision, ip)
        return Response(status_code=204)
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")
