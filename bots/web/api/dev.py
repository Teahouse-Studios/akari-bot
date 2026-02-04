import mimetypes
import os
from datetime import datetime
from pathlib import Path

import shutil
import tempfile
import zipfile

from fastapi import HTTPException, Request, File, Form, UploadFile
from fastapi.responses import Response, FileResponse, PlainTextResponse
from tortoise import Tortoise
from tortoise.exceptions import OperationalError

from bots.web.client import app
from core.constants import dev_mode
from core.database import fetch_module_db, get_model_fields, get_model_names
from core.logger import Logger
from .auth import verify_jwt

ROOT_DIR = Path(__file__).parent.parent.parent.parent


@app.get("/api/dev")
async def is_dev(request: Request):
    verify_jwt(request)
    return {"is_dev": dev_mode}


if dev_mode:
    @app.get("/api/dev/database/list")
    async def get_db_model_list(request: Request):
        try:
            verify_jwt(request)

            models_path = ["core.database.models"] + fetch_module_db()
            table_lst = sorted(get_model_names(models_path))
            return {"model_list": table_lst}
        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")

    @app.get("/api/dev/database/field/{model}")
    async def get_db_model_fields(request: Request, model: str):
        try:
            verify_jwt(request)

            models_path = ["core.database.models"] + fetch_module_db()
            result = get_model_fields(models_path, model)
            return {"model_fields": result}
        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")

    @app.post("/api/dev/database/exec")
    async def exec_sql(request: Request):
        ip = request.client.host
        try:
            verify_jwt(request)

            body = await request.json()
            sql = body.get("sql", "")

            conn = Tortoise.get_connection("default")

            if sql.upper().startswith("SELECT"):
                rows = await conn.execute_query_dict(sql)
                Logger.info(f"[WebUI] {ip} successfully executed SQL: \"{sql}\"")
                return {"success": True, "data": rows}
            rows, _ = await conn.execute_query(sql)
            Logger.info(f"[WebUI] {ip} successfully executed SQL: \"{sql}\", affecting {rows} rows of data.")
            return {"success": True, "affected_rows": rows}
        except OperationalError as e:
            Logger.warning(f"[WebUI] {ip} failed to execute SQL: \"{sql}\"")
            return {"success": False, "error": str(e)}
        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")

    def _secure_path(path: str) -> tuple[Path, str]:
        try:
            if len(str(path)) > 256:
                raise ValueError
            path = os.path.normpath(path)
            full_path = (ROOT_DIR / path).resolve()
            display_path = f"./{full_path.relative_to(ROOT_DIR).as_posix()}"
        except ValueError:
            raise HTTPException(status_code=403, detail="Forbidden")
        return full_path, display_path

    def _format_file_info(p: Path):
        return {
            "name": p.name,
            "is_dir": p.is_dir(),
            "size": p.stat().st_size,
            "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat()
        }

    @app.get("/api/dev/files/list")
    def list_files(request: Request, path: str = ""):
        try:
            verify_jwt(request)

            target, _ = _secure_path(path)
            if not target.exists() or not target.is_dir():
                raise HTTPException(status_code=404, detail="Not found")
            files = [
                _format_file_info(f) for f in sorted(
                    target.iterdir(),
                    key=lambda x: (
                        not x.is_dir(),
                        x.name.lower()))]
            return {"path": str(target.relative_to(ROOT_DIR)), "files": files}
        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")

    @app.get("/api/dev/files/download")
    def download_file(request: Request, path: str):
        ip = request.client.host
        try:
            verify_jwt(request)

            target, display_path = _secure_path(path)
            if not target.exists():
                raise HTTPException(status_code=404, detail="Not found")

            if target.is_file():
                Logger.info(f"[WebUI] {ip} downloaded file: \"{display_path}\"")
                return FileResponse(target, filename=target.name)

            temp_dir = tempfile.mkdtemp()
            zip_name = f"{target.name}.zip"
            zip_path = Path(temp_dir) / zip_name
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in target.rglob("*"):
                    zipf.write(file, file.relative_to(target))
            Logger.info(f"[WebUI] {ip} downloaded file: \"{display_path}.zip\"")
            return FileResponse(zip_path, filename=zip_name)
        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")

    @app.delete("/api/dev/files/delete")
    def delete_file(request: Request, path: str):
        ip = request.client.host
        try:
            verify_jwt(request)

            target, display_path = _secure_path(path)
            if target == ROOT_DIR:
                Logger.warning(f"[WebUI] {ip} failed to delete path: \"{display_path}\"")
                raise HTTPException(status_code=403, detail="Cannot delete root directory")

            if target.is_file():
                target.unlink()
                Logger.info(f"[WebUI] {ip} deleted file: \"{display_path}\"")
            elif target.is_dir():
                shutil.rmtree(target)
                Logger.info(f"[WebUI] {ip} deleted dir: \"{display_path}\"")
            else:
                Logger.warning(f"[WebUI] {ip} failed to delete path: \"{display_path}\"")
                raise HTTPException(status_code=404, detail="Not found")
            return Response(status_code=204)
        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")

    @app.post("/api/dev/files/rename")
    async def rename_file(request: Request):
        ip = request.client.host
        try:
            verify_jwt(request)

            body = await request.json()
            new_name = body.get("new_name", "")
            old_target, old_display_path = _secure_path(body.get("path", ""))
            new_target, new_display_path = _secure_path(old_target.parent / new_name)

            if old_target == ROOT_DIR:
                Logger.warning(f"[WebUI] {ip} failed to rename path: \"{old_display_path}\"")
                raise HTTPException(status_code=403, detail="Cannot rename root directory")
            if old_target.is_dir():
                try:
                    new_target.relative_to(old_target)
                    Logger.warning(f"[WebUI] {ip} failed to rename path: \"{old_display_path}\"")
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot move a directory into itself"
                    )
                except ValueError:
                    pass
            if new_target.exists():
                Logger.warning(f"[WebUI] {ip} failed to rename path: \"{old_display_path}\"")
                raise HTTPException(
                    status_code=409,
                    detail=f"Path '{new_name}' already exists"
                )

            new_target.parent.mkdir(parents=True, exist_ok=True)
            old_target.rename(new_target)
            Logger.info(f"[WebUI] {ip} renamed path: \"{old_display_path}\" -> \"{new_display_path}\"")
            return Response(status_code=204)
        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")

    @app.post("/api/dev/files/upload")
    def upload_file(request: Request, path: str = Form(""), file: UploadFile = File(...)):
        ip = request.client.host
        try:
            verify_jwt(request)

            target_dir, display_path = _secure_path(path)
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)

            safe_name = Path(file.filename).name
            target_file = target_dir / safe_name

            MAX_UPLOAD_SIZE = 10 * 1024 * 1024
            content = file.file.read(MAX_UPLOAD_SIZE + 1)
            if len(content) > MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=413, detail="File too large")

            with target_file.open("wb") as f:
                f.write(content)

            Logger.info(f"[WebUI] {ip} uploaded file: \"{display_path}\"")
            return Response(status_code=204)
        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")

    @app.post("/api/dev/files/create")
    def create_file_or_dir(request: Request, path: str = "", name: str = "", filetype: str = ""):
        ip = request.client.host
        try:
            verify_jwt(request)

            target, display_path = _secure_path((Path(path) / name).as_posix())
            if filetype == "dir":
                target.mkdir(parents=True, exist_ok=True)
                Logger.info(f"[WebUI] {ip} created dir: \"{display_path}\"")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch(exist_ok=True)
                Logger.info(f"[WebUI] {ip} created file: \"{display_path}\"")
            return Response(status_code=204)
        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")

    @app.get("/api/dev/files/preview")
    def preview_file(request: Request, path: str):
        try:
            verify_jwt(request)

            target, _ = _secure_path(path)
            if not target.is_file():
                raise HTTPException(status_code=404, detail="Not found")

            mime_type, _ = mimetypes.guess_type(target)

            if mime_type and mime_type.startswith("image"):
                return FileResponse(target, media_type=mime_type)

            if target.stat().st_size > 1024 * 1024:
                raise HTTPException(status_code=408, detail="File is too large")

            try:
                content = target.read_text(encoding="utf-8")
                return PlainTextResponse(content)
            except UnicodeDecodeError:
                return {"detail": "Unable to preview"}

        except HTTPException as e:
            raise e
        except Exception:
            Logger.exception()
            raise HTTPException(status_code=400, detail="Bad request")
