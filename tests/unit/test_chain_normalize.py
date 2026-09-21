"""消息链原地修改的归一化单元测试。"""

from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import PlainElement
from core.builtins.message.internal import Plain
from core.logger import Logger
from core.tester import func_case, Tester


async def _test_append_normalizes_str():
    try:
        chain = MessageChain.create()
        chain.append("裸字符串")
        if len(chain.values) != 1 or not isinstance(chain.values[0], PlainElement):
            Logger.error(f"append should normalise str, got: {chain.values!r}")
            return False
        return chain.values[0].text == "裸字符串"

    except Exception:
        return False


async def _test_appended_chain_is_serialisable():
    try:
        chain = MessageChain.create()
        chain.append("裸字符串")
        converter.unstructure(chain, MessageChain | MessageNodes)
        return True

    except Exception:
        Logger.exception()
        return False


async def _test_insert_normalizes_str():
    try:
        chain = MessageChain.assign(Plain("尾"))
        chain.insert(0, "头")
        return len(chain.values) == 2 and all(isinstance(v, PlainElement) for v in chain.values)

    except Exception:
        return False


async def _test_iadd_list_normalizes_str():
    try:
        chain = MessageChain.create()
        chain += [Plain("甲"), "乙"]
        return len(chain.values) == 2 and all(isinstance(v, PlainElement) for v in chain.values)

    except Exception:
        return False


async def _test_append_keeps_elements_intact():
    try:
        element = Plain("元素")
        chain = MessageChain.create()
        chain.append(element)
        return len(chain.values) == 1 and chain.values[0] is element

    except Exception:
        return False


async def _test_append_skips_empty_and_none():
    try:
        chain = MessageChain.create()
        chain.append("")
        chain.append(None)
        return len(chain.values) == 0

    except Exception:
        return False


@func_case
async def test_chain_normalize(tester: Tester):
    """消息链：原地修改的归一化测试"""
    await tester.test(_test_append_normalizes_str, "append 归一化字符串测试")
    await tester.test(_test_appended_chain_is_serialisable, "append 后可序列化测试")
    await tester.test(_test_insert_normalizes_str, "insert 归一化字符串测试")
    await tester.test(_test_iadd_list_normalizes_str, "+= 列表归一化测试")
    await tester.test(_test_append_keeps_elements_intact, "元素原样保留测试")
    await tester.test(_test_append_skips_empty_and_none, "空值跳过测试")

    return tester
