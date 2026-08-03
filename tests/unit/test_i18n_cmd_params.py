"""i18n 文案与调用点的参数一致性测试。

含 `${cmd}` 的文案若在某个调用点漏传该参数，用户会直接看到字面量
「使用“${cmd}”查看……」。此类漏传不会引发任何异常，测试不覆盖就只能靠肉眼。

同一个键在多处调用时尤其容易漏：曾有 `core.message.help.all_modules` 在图片版
分支传了 cmd、legacy 分支漏传，而按「该键至少有一处传了」来判定的检查放了过去。
故此处逐个调用点校验。
"""

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
    "core.bind.message.start.private.prompt",
    "core.bind.message.target.code.prompt",
    "core.merge.message.start.private.prompt",
    "core.merge.message.start.prompt",
}

# 上述键的 cmd 实际由该文件中的 issue_code() 补上
INDIRECT_PROVIDER = "core/union_merge.py"


def _iter_call_args(source: str, key: str):
    """取出源码中每一处以该键起头的调用的完整实参文本。

    以键名字面量为锚点，向前找到本次调用的左括号，再向后按括号配平找到右括号。

    :param source: 源码全文。
    :param key: i18n 键名。
    :return: 每处调用的实参片段。
    """
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
    """收集所有文案中含 ${cmd} 的键名。"""
    keys = set()
    for path in glob.glob("modules/*/locales/zh_cn.json") + [os.path.join("core", "locales", "zh_cn.json")]:
        with open(path, encoding="utf-8") as f:
            for key, value in json.load(f).items():
                if "${cmd}" in value:
                    keys.add(key)
    return keys


def _collect_sources() -> dict[str, str]:
    """读取模块与核心的全部源码。"""
    sources = {}
    for path in glob.glob("modules/**/*.py", recursive=True) + glob.glob("core/**/*.py", recursive=True):
        with open(path, encoding="utf-8") as f:
            sources[path.replace("\\", "/")] = f.read()
    return sources


def _test_every_call_passes_cmd():
    """测试含 ${cmd} 的文案在每一处调用点都传了该参数"""
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
    """测试间接传参的键确有补上 cmd 的去处

    白名单会掩盖真实的漏传，故要求其对应的补参代码仍然在位：
    issue_code() 一旦不再构造 ActionText，此处即失守。

    此处逐条报明缘由而不笼统吞掉异常：INDIRECT_PROVIDER 曾随文件迁移而失效，
    读不到文件的报错被 except 收成了断言不成立，看上去与「补参代码不在位」别无二致，
    白名单就此形同虚设却无人察觉。
    """
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
    """测试不存在只在文案中出现、代码里却无人引用的 ${cmd} 键

    改文案却忘了改调用点时，该键会成为孤儿，渲染出的仍是字面量。
    """
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
