"""消息链原地修改的归一化单元测试。

values 的声明类型是 list[MessageElement]，而 append 一类原地修改的方法此前直接写入
入参。裸字符串遂能一路活到 JobQueue 的序列化阶段，才以「'str' object is not a
mapping」暴露——彼时调用栈已深入 cattrs 内部，难以追溯是哪一处放进去的。

assign() 一向会把字符串转作文本元素，原地修改的方法却不会。两者行为不一致，正是
modules/wiki/wiki.py 与 modules/idlist 等处踩坑的由来：那些地方以
MessageChain.create() 起手，其后 append 的却是裸字符串。
"""

from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import PlainElement
from core.builtins.message.internal import Plain
from core.logger import Logger
from core.tester import func_case, Tester


async def _test_append_normalizes_str():
    """测试归一化 - append 裸字符串转作文本元素"""
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
    """测试归一化 - append 裸字符串后消息链仍可序列化

    这一条直接复现线上报错：finish() 收到的若已是 MessageChain，get_message_chain()
    便原样返回、跳过 assign 的归一化，裸字符串一路传至 cattrs 才抛
    TypeError: 'str' object is not a mapping。
    """
    try:
        chain = MessageChain.create()
        chain.append("裸字符串")
        converter.unstructure(chain, MessageChain | MessageNodes)
        return True

    except Exception:
        Logger.exception()
        return False


async def _test_insert_normalizes_str():
    """测试归一化 - insert 裸字符串转作文本元素"""
    try:
        chain = MessageChain.assign(Plain("尾"))
        chain.insert(0, "头")
        return len(chain.values) == 2 and all(isinstance(v, PlainElement) for v in chain.values)

    except Exception:
        return False


async def _test_iadd_list_normalizes_str():
    """测试归一化 - 以 += 并入的列表中的裸字符串一并转换"""
    try:
        chain = MessageChain.create()
        chain += [Plain("甲"), "乙"]
        return len(chain.values) == 2 and all(isinstance(v, PlainElement) for v in chain.values)

    except Exception:
        return False


async def _test_append_keeps_elements_intact():
    """测试归一化 - 传入的消息元素原样保留，不得误伤"""
    try:
        element = Plain("元素")
        chain = MessageChain.create()
        chain.append(element)
        return len(chain.values) == 1 and chain.values[0] is element

    except Exception:
        return False


async def _test_append_skips_empty_and_none():
    """测试归一化 - 空字符串与 None 一律跳过，与 assign 的取舍一致"""
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
