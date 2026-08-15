"""core.i18n 单元测试 - 语言快照的发布与重载。"""

import os
import tempfile
import time
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from uuid import uuid4

from core.i18n import Locale, build_locale_snapshot, connect_locale_snapshot
from core.tester import func_case, Tester


def _write_locale(path: Path, value: str) -> None:
    path.write_text(f'{{"snapshot":{{"value":"{value}"}}}}', encoding="utf-8")


def _test_locale_snapshot_reload():
    """测试语言重载 - 发布新快照并保留上一份可用快照。"""
    namespace = f"akari-bot-test-{uuid4().hex}"
    try:
        with tempfile.TemporaryDirectory(prefix="akari_locale_reload_") as directory:
            locale_file = Path(directory) / "zh_cn.json"
            _write_locale(locale_file, "before")

            if build_locale_snapshot(["zh_cn"], [directory], namespace):
                return False
            first_generation = connect_locale_snapshot(namespace)
            locale = Locale("zh_cn")
            if locale.t("snapshot.value", fallback=False, locale_failed_prompt=False) != "before":
                return False

            # 内容长度和 mtime 都保持不变，确保重载依赖内容签名而非文件元数据。
            stat = locale_file.stat()
            _write_locale(locale_file, "after!")
            os.utime(locale_file, ns=(stat.st_atime_ns, stat.st_mtime_ns))

            if build_locale_snapshot(["zh_cn"], [directory], namespace):
                return False
            # Reader 会定期检查共享 manifest，无需恢复旧的队列广播或显式重连。
            time.sleep(1.1)
            if locale.t("snapshot.value", fallback=False, locale_failed_prompt=False) != "after!":
                return False
            second_generation = connect_locale_snapshot(namespace)
            if first_generation == second_generation:
                return False

            # 临时写坏语言文件时应报告错误，但不能替换已经发布的健康快照。
            locale_file.write_text("{", encoding="utf-8")
            with redirect_stderr(StringIO()):
                errors = build_locale_snapshot(["zh_cn"], [directory], namespace)
            preserved_generation = connect_locale_snapshot(namespace)
            return (
                bool(errors)
                and preserved_generation == second_generation
                and locale.t("snapshot.value", fallback=False, locale_failed_prompt=False) == "after!"
            )
    except Exception:
        return False
    finally:
        # 后续测试仍应使用测试框架在启动时发布的项目语言快照。
        connect_locale_snapshot("akari-bot")


@func_case
async def test_locale_reload(tester: Tester):
    """core.i18n: 语言快照重载测试。"""
    await tester.test(_test_locale_snapshot_reload, "语言快照发布与回退测试")
    return tester
