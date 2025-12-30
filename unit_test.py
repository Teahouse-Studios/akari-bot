import os
import sys
import asyncio
import importlib.util
import traceback
from typing import List

from loguru import logger

from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.unit_test import get_registry

# Basic logger setup

try:
    logger.remove(0)
except ValueError:
    pass

Logger = logger.bind(name="uniTest")

logger_format = (
    "<cyan>[uniTest]</cyan>"
    "<level>[{level}]:{message}</level>"
)
Logger.add(
    sys.stdout,
    format=logger_format,
    level="INFO",
    colorize=True
)


class FakeMessageSession(MessageSession):
    def __init__(self, content: str):
        self.content = content
        self.sent = []
        self.parsed_msg = {}
        self.matched_msg = None
        parts = content.strip().split()
        if parts and parts[0].startswith("~") and len(parts) >= 2:
            if len(parts) >= 3:
                self.parsed_msg["<word>"] = " ".join(parts[2:])

    ...


async def _run_entry(entry: dict):
    func = entry["func"]
    inputs = entry["input"]

    if isinstance(inputs, str):
        inputs = [inputs]

    results = []
    for inp in inputs:
        msg = FakeMessageSession(inp)
        try:
            if asyncio.iscoroutinefunction(func):
                await func(msg)
            else:
                func(msg)
        except Exception:
            tb = traceback.format_exc()
            results.append({"input": inp, "error": tb, "sent": msg.sent})
            continue

        results.append({"input": inp, "sent": msg.sent})

    return results


def discover_and_import(paths: List[str]):
    for p in paths:
        if not os.path.exists(p):
            continue
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.endswith(".py"):
                        import_file(os.path.join(root, f))
        elif p.endswith(".py"):
            import_file(p)


def import_file(path: str):
    try:
        name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(f"unittest_imports.{name}", path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
    except ModuleNotFoundError:
        pass
    except Exception:
        Logger.error(f"Failed to import {path}:", file=sys.stderr)
        Logger.error(traceback.format_exc())


def main():
    paths = ["modules"]
    abs_paths = [os.path.join(os.getcwd(), p) for p in paths]
    discover_and_import(abs_paths)

    registry = get_registry()
    if not registry:
        Logger.error("No tests registered. Use `core.unittest.case` to register tests.")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    total = 0
    passed = 0

    for entry in registry:
        print("-" * 60)
        fn = entry["func"]
        Logger.info(f"Test: {fn.__name__}  ({entry.get('file')}:{entry.get('line')})")
        results = loop.run_until_complete(_run_entry(entry))

        for r in results:
            total += 1
            if "error" in r:
                Logger.error(f"INPUT: {r['input']}")
                Logger.error("ERROR during execution:")
                Logger.error(r["error"])
                continue

            sent = r.get("sent", [])
            expected = entry.get("expected")
            Logger.info(f"INPUT: {r['input']}")
            Logger.info("SENT:")
            for s in sent:
                print("  -", s)

            if expected is None:
                Logger.warning("EXPECTED: <manual check required>")
            else:
                ok = False
                if isinstance(expected, list):
                    ok = expected == sent
                else:
                    joined = "\n".join(map(str, sent))
                    ok = str(expected) == joined or (len(sent) == 1 and str(expected) == str(sent[0]))

                if ok:
                    Logger.success("RESULT: PASS")
                    passed += 1
                else:
                    Logger.error("RESULT: FAIL")
                    Logger.error("EXPECTED:", expected)

    print("-" * 60)
    Logger.info(f"Total: {total}, Passed: {passed}")


if __name__ == "__main__":
    main()
