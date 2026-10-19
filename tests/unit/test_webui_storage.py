"""bots.web.api.files 单元测试 - assets 与 data 文件管理接口。"""

import inspect
import zipfile
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

import bots.web.api.files as storage
from core.tester import Tester, func_case


class FakeRequest:
    def __init__(self, body=None):
        self._body = body

    async def json(self):
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


def _endpoint(func):
    return inspect.unwrap(func)


@contextmanager
def _patched(base: Path):
    with (
        patch.object(storage, "assets_path", base / "assets"),
        patch.object(storage, "data_path", base / "data"),
        patch.object(storage, "cache_path", base / "cache"),
        patch.object(storage, "modules_path", base / "modules"),
        patch.object(storage, "_module_names", lambda: ["alpha", "beta"]),
        patch.object(storage, "verify_jwt", lambda request: None),
        patch.object(storage, "get_client_ip", lambda request: "test"),
    ):
        yield


def _prepare(base: Path) -> None:
    (base / "assets").mkdir()
    (base / "data").mkdir()
    (base / "modules" / "alpha" / "data").mkdir(parents=True)
    (base / "modules" / "beta").mkdir(parents=True)


async def _call(call) -> tuple[int, object]:
    try:
        result = await call()
    except HTTPException as exc:
        return exc.status_code, exc.detail
    return getattr(result, "status_code", 200), result


def _call_sync(call) -> tuple[int, object]:
    try:
        result = call()
    except HTTPException as exc:
        return exc.status_code, exc.detail
    return getattr(result, "status_code", 200), result


async def _roots_case():
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        _prepare(base)
        with _patched(base):
            payload = await _endpoint(storage.get_storage_roots)(FakeRequest())

        roots = {item["id"]: item for item in payload["roots"]}
        assert set(roots) == {
            "core:assets",
            "core:data",
            "module:alpha:data",
        }
        assert roots["core:assets"]["scope"] == "core" and roots["core:assets"]["module"] is None
        assert roots["core:assets"]["target"] == "assets" and roots["core:assets"]["exists"] is True
        assert roots["module:alpha:data"]["scope"] == "module"
        assert roots["module:alpha:data"]["target"] == "data"
        assert roots["module:alpha:data"]["exists"] is True
        assert roots["module:alpha:data"]["path"].endswith(("modules/alpha/data", "modules\\alpha\\data"))
    return True


async def _list_case():
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        _prepare(base)
        data = base / "data"
        (data / "sub").mkdir()
        (data / "sub" / "b.txt").write_text("b", encoding="utf-8")
        (data / "alpha.txt").write_text("a", encoding="utf-8")

        with _patched(base):
            endpoint = _endpoint(storage.list_storage)

            listing = await endpoint(FakeRequest(), root="core:data")
            assert listing["exists"] is True and listing["path"] == ""
            assert [item["name"] for item in listing["files"]] == ["sub", "alpha.txt"]
            assert listing["files"][0]["is_dir"] is True and listing["files"][0]["revision"] is None
            assert listing["files"][1]["size"] == 1 and listing["files"][1]["revision"]

            nested = await endpoint(FakeRequest(), root="core:data", path="sub")
            assert [item["path"] for item in nested["files"]] == ["sub/b.txt"]

            missing = await endpoint(FakeRequest(), root="core:data", path="absent")
            assert missing == {"root": "core:data", "path": "absent", "exists": False, "files": []}

            assert await _call(lambda: endpoint(FakeRequest(), root="core:data", path="../outside")) == (
                403,
                "forbidden_path",
            )
            assert await _call(lambda: endpoint(FakeRequest(), root="core:data", path="..\\outside")) == (
                403,
                "forbidden_path",
            )
            assert await _call(lambda: endpoint(FakeRequest(), root="core:data", path="alpha.txt")) == (
                400,
                "not_a_directory",
            )
            assert await _call(lambda: endpoint(FakeRequest(), root="other:data")) == (404, "unknown_root")
            assert await _call(lambda: endpoint(FakeRequest(), root="module:beta:data")) == (404, "unknown_root")
            assert await _call(lambda: endpoint(FakeRequest(), root="module:alpha:assets")) == (
                404,
                "unknown_root",
            )
    return True


async def _content_case():
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        _prepare(base)
        data = base / "data"

        with _patched(base):
            write = _endpoint(storage.write_storage_content)
            read = _endpoint(storage.read_storage_content)

            created = await write(FakeRequest({"root": "core:data", "path": "notes/a.txt", "content": "hello"}))
            assert created["changed"] is True and created["entry"]["path"] == "notes/a.txt"
            assert (data / "notes" / "a.txt").read_text(encoding="utf-8") == "hello"

            loaded = await read(FakeRequest(), root="core:data", path="notes/a.txt")
            assert loaded["content"] == "hello" and loaded["revision"] == created["entry"]["revision"]

            module_write = await write(
                FakeRequest({"root": "module:alpha:data", "path": "state.json", "content": "{}"})
            )
            assert module_write["entry"]["path"] == "state.json"
            assert (base / "modules" / "alpha" / "data" / "state.json").read_text(encoding="utf-8") == "{}"

            assert await _call(
                lambda: write(FakeRequest({"root": "module:beta:assets", "path": "note.txt", "content": "note"}))
            ) == (404, "unknown_root")
            (base / "modules" / "beta" / "assets").mkdir()
            module_assets = await write(
                FakeRequest({"root": "module:beta:assets", "path": "note.txt", "content": "note"})
            )
            assert module_assets["entry"]["path"] == "note.txt"
            assert (base / "modules" / "beta" / "assets" / "note.txt").read_text(encoding="utf-8") == "note"

            assert await _call(
                lambda: write(
                    FakeRequest({"root": "core:data", "path": "notes/a.txt", "content": "x", "revision": "stale"})
                )
            ) == (409, "revision_mismatch")

            updated = await write(
                FakeRequest(
                    {
                        "root": "core:data",
                        "path": "notes/a.txt",
                        "content": "updated",
                        "revision": loaded["revision"],
                    }
                )
            )
            assert updated["entry"]["revision"] != loaded["revision"]
            assert (data / "notes" / "a.txt").read_text(encoding="utf-8") == "updated"

            (data / "folder").mkdir()
            assert await _call(lambda: read(FakeRequest(), root="core:data", path="folder")) == (
                400,
                "is_directory",
            )
            assert await _call(lambda: write(FakeRequest({"root": "core:data", "path": "folder", "content": "x"}))) == (
                400,
                "is_directory",
            )
            assert await _call(lambda: write(FakeRequest({"root": "core:data", "path": "", "content": "x"}))) == (
                400,
                "invalid_path",
            )
            assert await _call(lambda: write(FakeRequest({"root": "core:data", "path": "x.txt"}))) == (
                400,
                "invalid_body",
            )
            assert await _call(lambda: read(FakeRequest(), root="core:data", path="missing.txt")) == (
                404,
                "not_found",
            )

            (data / "bin.dat").write_bytes(b"\xff\xfe")
            assert await _call(lambda: read(FakeRequest(), root="core:data", path="bin.dat")) == (415, "not_text")

            (data / "big.txt").write_bytes(b"a" * (storage.MAX_CONTENT_BYTES + 1))
            assert await _call(lambda: read(FakeRequest(), root="core:data", path="big.txt")) == (
                413,
                "file_too_large",
            )
            assert await _call(
                lambda: write(
                    FakeRequest(
                        {
                            "root": "core:data",
                            "path": "big2.txt",
                            "content": "a" * (storage.MAX_CONTENT_BYTES + 1),
                        }
                    )
                )
            ) == (413, "file_too_large")
    return True


async def _entry_case():
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        _prepare(base)
        data = base / "data"

        with _patched(base):
            create = _endpoint(storage.create_storage_entry)
            rename = _endpoint(storage.rename_storage_entry)
            delete = _endpoint(storage.delete_storage_entry)

            made_dir = await create(FakeRequest({"root": "core:data", "path": "", "name": "sub", "type": "dir"}))
            assert made_dir["entry"]["is_dir"] is True and (data / "sub").is_dir()
            assert await _call(
                lambda: create(FakeRequest({"root": "core:data", "path": "", "name": "sub", "type": "dir"}))
            ) == (409, "already_exists")
            assert await _call(lambda: create(FakeRequest({"root": "core:data", "path": "", "name": "../x"}))) == (
                422,
                "invalid_name",
            )
            assert await _call(
                lambda: create(FakeRequest({"root": "core:data", "path": "", "name": "x", "type": "link"}))
            ) == (400, "invalid_type")

            made_file = await create(FakeRequest({"root": "core:data", "path": "sub", "name": "a.txt"}))
            assert (data / "sub" / "a.txt").is_file()
            assert made_file["entry"]["path"] == "sub/a.txt"

            renamed = await rename(FakeRequest({"root": "core:data", "path": "sub/a.txt", "new_name": "b.txt"}))
            assert renamed["entry"]["path"] == "sub/b.txt" and (data / "sub" / "b.txt").is_file()
            assert await _call(
                lambda: rename(FakeRequest({"root": "core:data", "path": "sub/b.txt", "new_name": "../evil"}))
            ) == (422, "invalid_name")
            assert await _call(
                lambda: rename(FakeRequest({"root": "core:data", "path": "sub", "new_name": "sub"}))
            ) == (400, "cannot_move_into_itself")
            assert await _call(lambda: rename(FakeRequest({"root": "core:data", "path": "", "new_name": "root"}))) == (
                403,
                "cannot_modify_root",
            )
            assert await _call(
                lambda: rename(FakeRequest({"root": "core:data", "path": "sub/missing", "new_name": "x"}))
            ) == (404, "not_found")

            (data / "sub" / "c.txt").write_text("c", encoding="utf-8")
            assert await _call(
                lambda: rename(FakeRequest({"root": "core:data", "path": "sub/b.txt", "new_name": "c.txt"}))
            ) == (409, "already_exists")

            status, _ = await _call(lambda: delete(FakeRequest(), root="core:data", path="sub/b.txt", revision="stale"))
            assert status == 409 and (data / "sub" / "b.txt").is_file()
            current = storage._file_revision(data / "sub" / "b.txt")
            status, _ = await _call(lambda: delete(FakeRequest(), root="core:data", path="sub/b.txt", revision=current))
            assert status == 204 and not (data / "sub" / "b.txt").exists()

            assert await _call(lambda: delete(FakeRequest(), root="core:data", path="")) == (
                403,
                "cannot_modify_root",
            )
            assert await _call(lambda: delete(FakeRequest(), root="core:data", path="missing")) == (
                404,
                "not_found",
            )
            status, _ = await _call(lambda: delete(FakeRequest(), root="core:data", path="sub"))
            assert status == 204 and not (data / "sub").exists()
    return True


async def _upload_case():
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        _prepare(base)
        data = base / "data"

        with _patched(base):
            upload = _endpoint(storage.upload_storage_file)
            download = _endpoint(storage.download_storage)

            created = await upload(
                FakeRequest(),
                root="core:data",
                path="uploads",
                file=UploadFile(file=BytesIO(b"hello"), filename="hello.txt"),
            )
            assert created["entry"]["path"] == "uploads/hello.txt"
            assert (data / "uploads" / "hello.txt").read_bytes() == b"hello"

            await upload(
                FakeRequest(),
                root="core:data",
                path="uploads",
                file=UploadFile(file=BytesIO(b"evil"), filename="../../evil.txt"),
            )
            assert (data / "uploads" / "evil.txt").read_bytes() == b"evil"
            assert not (base / "evil.txt").exists()

            with patch.object(storage, "MAX_UPLOAD_BYTES", 4):
                assert await _call(
                    lambda: upload(
                        FakeRequest(),
                        root="core:data",
                        path="upload_big",
                        file=UploadFile(file=BytesIO(b"12345"), filename="big.bin"),
                    )
                ) == (413, "file_too_large")

            file_response = download(FakeRequest(), root="core:data", path="uploads/hello.txt")
            assert Path(file_response.path) == data / "uploads" / "hello.txt"
            inline_response = download(FakeRequest(), root="core:data", path="uploads/hello.txt", inline=True)
            assert inline_response.headers["content-disposition"].startswith("inline")

            dir_response = download(FakeRequest(), root="core:data", path="uploads")
            with zipfile.ZipFile(dir_response.path) as archive:
                assert sorted(archive.namelist()) == ["evil.txt", "hello.txt"]
            await dir_response.background()
            assert not Path(dir_response.path).parent.exists()

            assert _call_sync(lambda: download(FakeRequest(), root="core:data", path="missing")) == (
                404,
                "not_found",
            )
    return True


@func_case
async def test_webui_storage(tester: Tester):
    """bots.web.api.files: assets 与 data 文件管理接口测试"""
    await tester.test(_roots_case, "资源根目录枚举与存在状态")
    await tester.test(_list_case, "目录列举、排序与路径穿越拦截")
    await tester.test(_content_case, "文本读取、写入、版本冲突与大小限制")
    await tester.test(_entry_case, "创建、重命名、删除与根目录保护")
    await tester.test(_upload_case, "上传、下载与目录压缩")

    return tester
