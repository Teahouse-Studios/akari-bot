import inspect

from core.logger import Logger
from .expectations import Expectation
from .process import run_test_case


class Tester:
    def __init__(self, name: str | None = None):
        self.name = name
        self._entries: list[dict] = []
        self._results: list[dict] = []
        self.is_ci: bool = False

    async def test(
        self,
        func: callable,
        note: str | None = None,
    ):
        """
        运行纯函数测试，不需要命令占位符。

        :param func: 测试函数或 Predicate，返回 True 表示通过，False 表示失败。
        :param note: 额外说明。
        :returns: 测试结果字典。
        """
        import asyncio

        Logger.trace(f"[{self.name}] test: {note or func.__name__}")

        frame = inspect.stack()[1]
        entry_meta = {
            "type": "unit",
            "expected": func,
            "note": note,
            "timeout": None,
            "file": frame.filename,
            "line": frame.lineno,
        }
        self._entries.append(entry_meta)

        if asyncio.iscoroutinefunction(func):
            result = await func()
        else:
            result = func()

        passed = bool(result)
        final = {
            "type": "unit",
            "input": None,
            "output": None,
            "action": [],
            "expected": func,
            "match": passed,
            "note": note,
        }
        self._results.append(final)
        return final

    async def integrate(
        self,
        input_: str | list[str] | tuple[str, ...],
        expected: Expectation | None = None,
        note: str | None = None,
        timeout: float | None = None,
    ):
        """
        注册一个交互测试案例。

        :param input_: 预期输入。
        :param expected: 预期输出，传入期望匹配器，若为 None 则手动复核。
        :param note: 额外说明。
        :param timeout: 超时时间（秒），若为 None 则无超时限制。
        """
        Logger.trace(f"[{self.name}] expect: {input_} - {note or ''}")

        frame = inspect.stack()[1]
        entry_meta = {
            "type": "integration",
            "input": input_,
            "expected": expected,
            "note": note,
            "timeout": timeout,
            "file": frame.filename,
            "line": frame.lineno,
        }
        self._entries.append(entry_meta)

        result = await run_test_case(input_, expected=expected, is_ci=self.is_ci, timeout=timeout)

        output = result.get("output")
        action = result.get("action")

        if "timeout" in result or "exception" in result and not isinstance(expected, Expectation):
            result.update({"expected": expected, "match": False, "note": note})
            self._results.append(result)
            return result

        if not expected:
            match = None
        elif isinstance(expected, Expectation):
            match = await expected.match(result)

        final = {
            "type": "integration",
            "input": input_,
            "output": output,
            "action": action,
            "expected": expected,
            "match": match,
            "note": note,
        }

        self._results.append(final)
        return final

    def get_entries(self) -> list[dict]:
        return list(self._entries)

    def get_results(self) -> list[dict]:
        return list(self._results)


__all__ = ["Tester"]
