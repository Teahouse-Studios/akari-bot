"""i18n 文案与调用点的参数一致性测试。"""

import glob
import json
import os
import re

from core.logger import Logger
from core.tester import func_case, Tester

# 以键名作为参数传入、由被调方统一补上 cmd 的调用点。
# issue_code() 接收 prompt_key 后在内部构造 ActionText，调用侧只写键名，
# 逐调用点扫描无从分辨，故列为已知例外。
KNOWN_INDIRECT_KEYS = {
    "core.message.bind.start.private.prompt",
    "core.message.bind.target.code.prompt",
    "core.message.bind.merge.start.private.prompt",
    "core.message.bind.merge.start.prompt",
}

# 上述键的 cmd 实际由该文件中的 issue_code() 补上
INDIRECT_PROVIDER = "core/utils/union_merge.py"


def _iter_call_args(source: str, key: str):
    for match in re.finditer(re.escape(f'"{key}"'), source):
        depth = 0
        left = match.start()
        while left > 0:
            left -= 1
            if source[left] == ")":
                depth += 1
            elif source[left] == "(":
                if depth == 0:
                    break
                depth -= 1
        depth = 0
        right = left
        while right < len(source):
            if source[right] == "(":
                depth += 1
            elif source[right] == ")":
                depth -= 1
                if depth == 0:
                    break
            right += 1
        yield source[left : right + 1]


def _collect_cmd_keys() -> set[str]:
    keys = set()
    for path in glob.glob("modules/*/locales/zh_cn.json") + [os.path.join("core", "locales", "zh_cn.json")]:
        with open(path, encoding="utf-8") as f:
            for key, value in json.load(f).items():
                if "${cmd}" in value:
                    keys.add(key)
    return keys


def _collect_sources() -> dict[str, str]:
    sources = {}
    for path in glob.glob("modules/**/*.py", recursive=True) + glob.glob("core/**/*.py", recursive=True):
        with open(path, encoding="utf-8") as f:
            sources[path.replace("\\", "/")] = f.read()
    return sources


def _test_every_call_passes_cmd():
    try:
        keys = _collect_cmd_keys()
        if not keys:
            return False
        sources = _collect_sources()
        for key in keys:
            if key in KNOWN_INDIRECT_KEYS:
                continue
            for path, source in sources.items():
                if f'"{key}"' not in source:
                    continue
                for call in _iter_call_args(source, key):
                    if "cmd=" not in call:
                        return False
        return True
    except Exception:
        return False


def _test_indirect_keys_have_provider():
    try:
        with open(INDIRECT_PROVIDER, encoding="utf-8") as f:
            provider = f.read()
    except OSError:
        Logger.error(f"{INDIRECT_PROVIDER} is unreadable; point INDIRECT_PROVIDER at where issue_code() now lives")
        return False
    if "cmd=ActionText(" not in provider:
        Logger.error(f"{INDIRECT_PROVIDER} no longer builds cmd=ActionText(); the whitelist would mask real omissions")
        return False
    # 白名单中的键须确实作为 prompt_key 流向该函数，而非无人问津
    sources = _collect_sources()
    for key in KNOWN_INDIRECT_KEYS:
        if not any(f'"{key}"' in source for source in sources.values()):
            Logger.error(f"Whitelisted key {key} is referenced nowhere; drop it from KNOWN_INDIRECT_KEYS")
            return False
    return True


def _test_no_stale_cmd_placeholder():
    try:
        keys = _collect_cmd_keys()
        sources = _collect_sources()
        for key in keys:
            if not any(f'"{key}"' in source for source in sources.values()):
                return False
        return True
    except Exception:
        return False


@func_case
async def test_i18n_cmd_params(tester: Tester):
    """i18n: ${cmd} 参数传递一致性测试"""
    await tester.test(_test_every_call_passes_cmd, "每处调用均传 cmd 测试")
    await tester.test(_test_indirect_keys_have_provider, "间接传参键的补参代码在位测试")
    await tester.test(_test_no_stale_cmd_placeholder, "无孤儿 cmd 键测试")

    return tester
