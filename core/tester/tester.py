import inspect

from .expectations import Expectation
from .process import run_test_case


class Tester:
    def __init__(self, name: str | None = None):
        self.name = name
        self._entries: list[dict] = []
        self._results: list[dict] = []
        self.is_ci: bool = False

    async def expect(
        self,
        input_: str | list[str] | tuple[str, ...],
        expected: Expectation | None = None,
        note: str | None = None,
        timeout: float | None = None,
    ):
        """
        注册一个测试案例。

        :param input_: 预期输入。
        :param expected: 预期输出，传入期望匹配器，若为 None 则手动复核。
        :param note: 额外说明。
        :param timeout: 超时时间（秒），若为 None 则无超时限制。
        """
        frame = inspect.stack()[1]
        entry_meta = {
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
