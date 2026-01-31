import inspect

from core.builtins.message.chain import MessageChain
from core.builtins.types import MessageElement
from .decorator import case, func_case
from .process import run_single_test, match_expected


class Tester:
    def __init__(self, name: str | None = None):
        self.name = name
        self._entries: list[dict] = []
        self._results: list[dict] = []
        self.is_ci: bool = False

    async def input(
        self,
        input_: str | list[str] | tuple[str, ...],
        expected:
            bool |
            str |
            MessageChain |
            list[MessageElement] |
            tuple[MessageElement, ...] |
            MessageElement |
            None = None,
        note: str | None = None,
    ):
        frame = inspect.stack()[1]
        entry_meta = {
            "input": input_,
            "expected": expected,
            "note": note,
            "file": frame.filename,
            "line": frame.lineno,
        }
        self._entries.append(entry_meta)

        result = await run_single_test(input_, is_ci=self.is_ci)

        if "error" in result or "exception" in result:
            result.update({"expected": expected, "match": False, "note": note})
            self._results.append(result)
            return result

        output = result.get("output")
        action = result.get("action")
        match = await match_expected(output, expected)

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


__all__ = ["case", "func_case", "Tester"]
