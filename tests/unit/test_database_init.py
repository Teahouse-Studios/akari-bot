"""数据库连接参数与初始化职责单元测试。"""

from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock, patch

import core.database as database
from core.database.link import prepare_db_link
from core.tester import Tester, func_case


def _query_fields(link: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(link).query)


def _test_sqlite_defaults_are_added():
    link = prepare_db_link("sqlite://database/save.db")
    fields = _query_fields(link)
    return fields.get("journal_mode") == ["WAL"] and fields.get("busy_timeout") == ["30000"]


def _test_sqlite_explicit_fields_are_preserved():
    link = prepare_db_link("sqlite://database/save.db?busy_timeout=1000&journal_mode=DELETE&cache_size=2000")
    fields = _query_fields(link)
    return (
        fields.get("busy_timeout") == ["1000"]
        and fields.get("journal_mode") == ["DELETE"]
        and fields.get("cache_size") == ["2000"]
    )


def _test_non_sqlite_link_keeps_existing_behavior():
    link = prepare_db_link("mysql+asyncmy://user:pass@localhost/akari?charset=utf8mb4")
    return link == "mysql://user:pass@localhost/akari?charset=utf8mb4"


async def _test_runtime_init_does_not_generate_schemas():
    init = AsyncMock()
    generate_schemas = AsyncMock()
    old_database_list = database.Temp.data.get("modules_db_list")
    try:
        with (
            patch.object(database, "fetch_module_db", return_value=["modules.example.database.models"]),
            patch.object(database, "get_db_link", return_value="sqlite://database/save.db"),
            patch.object(database.Tortoise, "init", new=init),
            patch.object(database.Tortoise, "generate_schemas", new=generate_schemas),
        ):
            result = await database.init_db()

        config = init.await_args.kwargs["config"]
        return (
            result
            and generate_schemas.await_count == 0
            and config["apps"]["models"]["models"] == ["core.database.models", "modules.example.database.models"]
            and _query_fields(config["connections"]["local"]).get("busy_timeout") == ["30000"]
        )
    finally:
        if old_database_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_database_list


async def _test_pre_init_mode_generates_all_schemas():
    init = AsyncMock()
    generate_schemas = AsyncMock()
    old_database_list = database.Temp.data.get("modules_db_list")
    try:
        with (
            patch.object(database, "fetch_module_db", return_value=["modules.example.database.models"]),
            patch.object(database.Tortoise, "init", new=init),
            patch.object(database.Tortoise, "generate_schemas", new=generate_schemas),
        ):
            result = await database.init_db(generate_schemas=True)

        config = init.await_args.kwargs["config"]
        return (
            result
            and generate_schemas.await_count == 1
            and generate_schemas.await_args.kwargs == {"safe": True}
            and "modules.example.database.models" in config["apps"]["models"]["models"]
            and config["apps"]["local_models"]["models"] == ["core.database.local"]
        )
    finally:
        if old_database_list is None:
            database.Temp.data.pop("modules_db_list", None)
        else:
            database.Temp.data["modules_db_list"] = old_database_list


@func_case
async def test_database_init(tester: Tester):
    """SQLite 参数自动补全，且仅 pre-init 模式执行建表。"""
    await tester.test(_test_sqlite_defaults_are_added, "SQLite 缺失参数自动补全")
    await tester.test(_test_sqlite_explicit_fields_are_preserved, "SQLite 显式参数保持不变")
    await tester.test(_test_non_sqlite_link_keeps_existing_behavior, "非 SQLite 连接保持现有行为")
    await tester.test(_test_runtime_init_does_not_generate_schemas, "运行期初始化不执行建表")
    await tester.test(_test_pre_init_mode_generates_all_schemas, "pre-init 建立核心、local 与模块表")
    return tester
