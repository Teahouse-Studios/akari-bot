import inspect
import traceback
from typing import Callable, List, Optional, Tuple, Union

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.elements import PlainElement
from core.builtins.types import MessageElement
from core.constants.exceptions import AbuseWarning, FinishedException, NoReportException, TestException
from core.cooldown import _cd_dict
from core.database.models import SenderInfo, TargetInfo
from core.game import _ps_dict
from core.tester.mock.session import MockMessageSession
from core.tester.mock.parser import parser

_REGISTRY: List[dict] = []


def case(input_: str,
         expected: Optional[Union[bool,
                                  str,
                                  MessageChain,
                                  list[MessageElement],
                                  Tuple[MessageElement],
                                  MessageElement]] = None,
         manual: bool = False,
         note: Optional[str] = None):
    """
    快捷注册一个测试案例。

    示例：
    ```
    @case("~test say Hello", "Hello is Hello")
    @test.command("say <word>")
    async def _(msg: Bot.MessageSession, word: str):
        await msg.finish(f"{word} is {msg.parsed_msg["<word>"]}")
    ```
    :param input: 预期输入。
    :param expected: 预期输出，若为 bool 则表示是否存在输出，否则将对比预期输出。
    :param manual: 是否使用人工检查。
    :param note: 额外说明。
    """

    def _decorator(fn: Callable):
        entry = {
            "func": fn,
            "input": input_,
            "expected": expected,
            "manual": manual,
            "note": note,
            "file": inspect.getsourcefile(fn),
            "line": inspect.getsourcelines(fn)[1],
        }
        _REGISTRY.append(entry)

        setattr(fn, "_casetest_meta", entry)

        return fn

    return _decorator


def get_registry():
    return list(_REGISTRY)


async def run_registry(entry: dict):
    func = entry["func"]
    input_ = entry["input"]

    try:
        await TargetInfo.update_or_create(defaults={}, target_id="TEST|Console|0")
        await SenderInfo.update_or_create(defaults={"superuser": True}, sender_id="TEST|0")
    except Exception:
        pass

    results = []
    msg = MockMessageSession(input_)
    await msg.async_init(input_)
    setattr(msg, "_casetest_target", func)
    try:
        await parser(msg)
    except FinishedException:
        pass
    except (AbuseWarning, NoReportException, TestException) as e:
        err_msg = msg.session_info.locale.t_str(str(e))
        err_msg_chain = match_kecode(err_msg, disable_joke=True)
        err_action = [x.text if isinstance(x, PlainElement) else str(x)
                      for x in err_msg_chain.as_sendable(msg.session_info)]
        results.append({"input": input_, "output": err_msg_chain, "action": [
                       f"(raise {type(e).__name__})"] + err_action})
        return results
    except Exception:
        tb = traceback.format_exc()
        results.append({"input": input_, "error": tb})
        return results
    finally:
        # cleanup
        _cd_dict.clear()
        _ps_dict.clear()

    results.append({"input": input_, "output": msg.sent, "action": msg.action})
    return results

__all__ = ["case", "get_registry", "run_registry"]
