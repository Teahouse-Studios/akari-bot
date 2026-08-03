"""临时的单测运行脚本，仅用于开发期跑单个测试入口。

自研测试框架的 tester.py 会 glob 全部用例且无过滤参数，逐个验证时过于笨重。
此脚本按文件与函数名跑单个入口，并在收尾时强制退出——框架加载的模块会留下
未完成的后台任务，不强制退出会一直挂到超时。

用法：uv run --no-sync python tests/run_one.py <文件路径> <入口函数名>
"""

import asyncio
import importlib.util
import os
import sys
import traceback
from pathlib import Path

# 以文件路径直接启动时，sys.path 首位是 tests/ 而非项目根，须先补上才能 import core
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.process import run_function_entry


async def main(path: str, entry: str) -> int:
    """
    跑单个测试入口并打印每条用例的结果。

    :param path: 测试文件路径。
    :param entry: 入口函数名。
    :return: 进程退出码，全部通过为 0。
    """
    await init_db()
    await load_modules(show_logs=False, monkey_patches={"Random": Random()})

    spec = importlib.util.spec_from_file_location("one", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["one"] = mod
    spec.loader.exec_module(mod)

    failed = 0
    entries = [entry] if entry else [n for n in dir(mod) if n.startswith("test_")]
    for name in entries:
        res = await run_function_entry(getattr(mod, name), is_ci=True)
        print(f"=== {name} ===")
        for r in res.get("results", []):
            status = "PASS" if r.get("match") else "FAIL"
            if not r.get("match"):
                failed += 1
            label = r.get("note") or r.get("input") or r.get("expected") or "?"
            print(f"  [{status}] {label}")
            if not r.get("match"):
                print(f"         action={r.get('action')} detail={r}")
        if res.get("error"):
            failed += 1
            print(f"  ERROR: {res.get('error')}")

    await close_db()
    return 1 if failed else 0


if __name__ == "__main__":
    target_path = sys.argv[1]
    target_entry = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        code = asyncio.run(main(target_path, target_entry))
    except Exception:
        traceback.print_exc()
        code = 1
    # 框架加载的模块会留下未完成的后台任务，正常返回会挂起，故强制退出
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
