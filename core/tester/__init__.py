import inspect
from typing import List, Optional, Union, Tuple

from core.builtins.message.chain import MessageChain
from core.builtins.types import MessageElement
from core.logger import Logger
from core.tester.process import match_expected, run_single_test
from .decorator import *


class Tester:
    def __init__(self, name: Optional[str] = None):
        self.name = name
        self._entries: List[dict] = []
        self._results: List[dict] = []
        self.is_ci: bool = False

    async def input(
        self,
        input_: Union[str, list[str], Tuple[str]],
        expected: Optional[Union[
            bool,
            str,
            MessageChain,
            list[MessageElement],
            Tuple[MessageElement],
            MessageElement,
        ]] = None,
        note: Optional[str] = None,
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

        if not output:
            try:
                Logger.debug(
                    "Tester debug - trigger: %s, parsed: %s, sent: %s, action: %s",
                    input_,
                    getattr(result, "parsed_msg", None),
                    output,
                    action,
                )
            except Exception:
                pass

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

    def get_entries(self) -> List[dict]:
        return list(self._entries)

    def get_results(self) -> List[dict]:
        return list(self._results)


__all__ = ["case", "func_case", "Tester"]
