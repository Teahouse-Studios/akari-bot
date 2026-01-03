import inspect
import traceback
from typing import List, Optional, Union, Tuple

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.elements import PlainElement
from core.builtins.types import MessageElement
from core.constants.exceptions import (
    AbuseWarning,
    FinishedException,
    NoReportException,
    TestException,
)
from core.cooldown import _cd_dict
from core.database.models import SenderInfo, TargetInfo
from core.game import _ps_dict
from core.tester.mock.session import MockMessageSession
from core.tester.mock.parser import parser
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from .decorator import *


class Tester:
    def __init__(self, name: Optional[str] = None):
        self.name = name
        self._entries: List[dict] = []
        self._results: List[dict] = []

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

        result = await _run_single_test(input_)

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

        match = await _match_expected(output, expected)

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


async def run_registry(entry: dict):
    result = await _run_single_test(
        entry["input"],
        casetest_target=entry.get("func"),
    )
    return [result]


async def _run_single_test(
    input_: Union[str, list[str], Tuple[str]],
    *,
    casetest_target=None,
):
    try:
        await TargetInfo.update_or_create(defaults={}, target_id="TEST|Console|0")
        await SenderInfo.update_or_create(defaults={"superuser": True}, sender_id="TEST|0")
    except Exception:
        pass

    msg = MockMessageSession(input_)
    await msg.async_init(msg.trigger_msg)

    if casetest_target is not None:
        setattr(msg, "_casetest_target", casetest_target)

    try:
        await parser(msg)
    except FinishedException:
        pass
    except (AbuseWarning, NoReportException, TestException) as e:
        err_msg = msg.session_info.locale.t_str(str(e))
        try:
            err_chain = match_kecode(err_msg, disable_joke=True)
        except Exception:
            err_chain = MessageChain(err_msg)

        err_action = [
            x.text if isinstance(x, PlainElement) else str(x)
            for x in err_chain.as_sendable(msg.session_info)
        ]

        return {
            "input": input_,
            "output": err_chain,
            "action": [f"(raise {type(e).__name__})"] + err_action,
            "exception": type(e).__name__,
        }
    except Exception:
        return {
            "input": input_,
            "error": traceback.format_exc(),
        }
    finally:
        _cd_dict.clear()
        _ps_dict.clear()

    return {
        "input": input_,
        "output": msg.sent,
        "action": msg.action,
    }


async def _match_expected(
    output,
    expected: Optional[Union[bool, str, MessageChain, list[MessageElement], Tuple[MessageElement], MessageElement]],
) -> Optional[bool]:
    if expected is None:  # noqa
        return None
    if expected is True:  # noqa
        return bool(output)
    if expected is False:  # noqa
        return not bool(output)

    session_info = await SessionInfo.assign(
        target_id="TEST|Console|0",
        client_name="TEST",
        target_from="TEST",
        sender_id="TEST|0",
        sender_from="TEST",
    )

    expected_chain = MessageChain.assign(expected).as_sendable(session_info)
    return output == expected_chain


__all__ = ["case", "func_case", "Tester", "get_registry", "run_registry"]
