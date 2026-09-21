"""bots.web.api 单元测试 - 配置文件删除接口（临时目录）。"""

import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import HTTPException

import bots.web.api.api as web_api
from core.tester import Tester, func_case


async def _call(call) -> tuple[int, object]:
    try:
        result = await call()
    except HTTPException as exc:
        return exc.status_code, exc.detail
    return getattr(result, "status_code", 200), result


def _patched(directory: Path):
    return (
        patch.object(web_api, "config_path", directory),
        patch.object(web_api, "verify_jwt", lambda request: None),
        patch.object(web_api, "get_client_ip", lambda request: "test"),
    )


async def _test_delete_config_file_removes_file():
    endpoint = inspect.unwrap(web_api.delete_config_file)
    with TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir)
        (directory / "config.toml").write_text("[config]\n", encoding="utf-8")
        (directory / "module_probe.toml").write_text("probe_value = 1\n", encoding="utf-8")
        config_patch, jwt_patch, ip_patch = _patched(directory)
        with config_patch, jwt_patch, ip_patch:
            result = await endpoint(None, "module_probe.toml")
            if result["changed"] is not True or result["restart_required"] is not True:
                return False
            if (directory / "module_probe.toml").exists():
                return False
            # 主配置置顶，已删除的文件不再出现在列表中
            if result["cfg_files"] != ["config.toml"]:
                return False

            again = await endpoint(None, "module_probe.toml")
            return again["changed"] is False and again["cfg_files"] == ["config.toml"]


async def _test_delete_config_file_rejects_unsafe_names():
    endpoint = inspect.unwrap(web_api.delete_config_file)
    with TemporaryDirectory() as temp_dir:
        directory = Path(temp_dir)
        (directory / "config.toml").write_text("[config]\n", encoding="utf-8")
        config_patch, jwt_patch, ip_patch = _patched(directory)
        with config_patch, jwt_patch, ip_patch:
            protected = await _call(lambda: endpoint(None, "config.toml"))
            suffix = await _call(lambda: endpoint(None, "notes.txt"))
            nested = await _call(lambda: endpoint(None, "sub/module_probe.toml"))
            escaped = await _call(lambda: endpoint(None, "../outside.toml"))
        return (
            protected == (403, "protected_config")
            and suffix == (400, "invalid_config_name")
            and nested == (400, "invalid_config_name")
            and escaped == (400, "invalid_config_name")
            and (directory / "config.toml").exists()
        )


async def _test_delete_config_file_reports_missing_config_dir():
    endpoint = inspect.unwrap(web_api.delete_config_file)
    with TemporaryDirectory() as temp_dir:
        missing = Path(temp_dir) / "absent"
        config_patch, jwt_patch, ip_patch = _patched(missing)
        with config_patch, jwt_patch, ip_patch:
            return await _call(lambda: endpoint(None, "module_probe.toml")) == (404, "config_dir_not_found")


@func_case
async def test_webui_config_delete(tester: Tester):
    """bots.web.api: 配置文件删除接口测试"""
    await tester.test(_test_delete_config_file_removes_file, "删除配置文件测试")
    await tester.test(_test_delete_config_file_rejects_unsafe_names, "删除配置文件校验测试")
    await tester.test(_test_delete_config_file_reports_missing_config_dir, "配置目录缺失测试")

    return tester
