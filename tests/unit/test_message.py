"""core.builtins.message 消息系统单元测试。"""

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import (
    PlainElement,
    URLElement,
    ImageElement,
    MentionElement,
    EmbedElement,
)
from core.builtins.message.internal import (
    Plain,
    Url,
    I18NContext,
)
from core.tester import func_case, Tester


def _test_assign_from_string():
    """测试从字符串创建消息链"""
    try:
        chain = MessageChain.assign("Hello World")
        if not isinstance(chain, MessageChain):
            return False
        if len(chain.values) != 1:
            return False
        if not isinstance(chain.values[0], PlainElement):
            return False
        if chain.values[0].text != "Hello World":
            return False
        return True
    except Exception:
        return False


def _test_assign_from_none():
    """测试从 None 创建空消息链"""
    try:
        chain = MessageChain.assign(None)
        if not isinstance(chain, MessageChain):
            return False
        if len(chain.values) != 0:
            return False
        return True
    except Exception:
        return False


def _test_assign_from_element():
    """测试从单个元素创建消息链"""
    try:
        elem = PlainElement.assign("Test")
        chain = MessageChain.assign(elem)
        if not isinstance(chain, MessageChain):
            return False
        if len(chain.values) != 1:
            return False
        if chain.values[0].text != "Test":
            return False
        return True
    except Exception:
        return False


def _test_assign_from_list():
    """测试从列表创建消息链"""
    try:
        elems = [PlainElement.assign("A"), PlainElement.assign("B")]
        chain = MessageChain.assign(elems)
        if not isinstance(chain, MessageChain):
            return False
        if len(chain.values) != 2:
            return False
        if chain.values[0].text != "A":
            return False
        if chain.values[1].text != "B":
            return False
        return True
    except Exception:
        return False


def _test_assign_from_tuple():
    """测试从元组创建消息链"""
    try:
        elems = (PlainElement.assign("X"), PlainElement.assign("Y"))
        chain = MessageChain.assign(elems)
        if not isinstance(chain, MessageChain):
            return False
        if len(chain.values) != 2:
            return False
        return True
    except Exception:
        return False


def _test_assign_from_message_chain():
    """测试从 MessageChain 创建消息链"""
    try:
        chain1 = MessageChain.assign("Original")
        chain2 = MessageChain.assign(chain1)
        if chain1 is not chain2:
            return False
        return True
    except Exception:
        return False


def _test_assign_empty_string():
    """测试空字符串处理"""
    try:
        chain = MessageChain.assign("")
        if not isinstance(chain, MessageChain):
            return False
        if len(chain.values) != 1:
            return False
        if not isinstance(chain.values[0], PlainElement):
            return False
        if chain.values[0].text != "":
            return False
        return True
    except Exception:
        return False


def _test_assign_mixed_list():
    """测试混合类型列表"""
    try:
        elems = ["text1", PlainElement.assign("text2")]
        chain = MessageChain.assign(elems)
        if len(chain.values) != 2:
            return False
        return True
    except Exception:
        return False


def _test_to_str():
    """测试 to_str() 方法"""
    try:
        chain = MessageChain.assign("Hello World")
        result = chain.to_str()
        if result != "Hello World":
            return False
        return True
    except Exception:
        return False


def _test_to_str_multiple():
    """测试多个元素的 to_str()"""
    try:
        chain = MessageChain.assign([PlainElement.assign("Hello "), PlainElement.assign("World")])
        result = chain.to_str()
        if "Hello" not in result or "World" not in result:
            return False
        return True
    except Exception:
        return False


def _test_len():
    """测试消息链长度"""
    try:
        chain = MessageChain.assign([PlainElement.assign("A"), PlainElement.assign("B")])
        if len(chain) != 2:
            return False
        return True
    except Exception:
        return False


def _test_len_empty():
    """测试空消息链长度"""
    try:
        chain = MessageChain.assign(None)
        if len(chain) != 0:
            return False
        return True
    except Exception:
        return False


def _test_plain_element_assign():
    """测试 PlainElement.assign()"""
    try:
        elem = PlainElement.assign("Hello")
        if not isinstance(elem, PlainElement):
            return False
        if elem.text != "Hello":
            return False
        return True
    except Exception:
        return False


def _test_plain_element_multiple_args():
    """测试 PlainElement.assign() 多参数"""
    try:
        elem = PlainElement.assign("Hello", " ", "World")
        if elem.text != "Hello World":
            return False
        return True
    except Exception:
        return False


def _test_plain_element_str():
    """测试 PlainElement.__str__()"""
    try:
        elem = PlainElement.assign("Test")
        if str(elem) != "Test":
            return False
        return True
    except Exception:
        return False


def _test_plain_element_kecode():
    """测试 PlainElement.kecode()"""
    try:
        elem = PlainElement.assign("Hello")
        kecode = elem.kecode()
        if "[KE:plain,text=Hello]" != kecode:
            return False
        return True
    except Exception:
        return False


def _test_plain_element_kecode_disable_joke():
    """测试 PlainElement.kecode() 禁用玩笑"""
    try:
        elem = PlainElement.assign("Hello", disable_joke=True)
        kecode = elem.kecode()
        if "[KE:plain,text=Hello,disable_joke=1]" != kecode:
            return False
        return True
    except Exception:
        return False


def _test_url_element_assign():
    """测试 URLElement.assign()"""
    try:
        elem = URLElement.assign("https://example.com")
        if not isinstance(elem, URLElement):
            return False
        if elem.url != "https://example.com":
            return False
        return True
    except Exception:
        return False


def _test_url_element_str():
    """测试 URLElement.__str__()"""
    try:
        elem = URLElement.assign("https://example.com")
        if str(elem) != "https://example.com":
            return False
        return True
    except Exception:
        return False


def _test_plain_alias():
    """测试 Plain 别名"""
    try:
        elem = Plain("Hello")
        if not isinstance(elem, PlainElement):
            return False
        if elem.text != "Hello":
            return False
        return True
    except Exception:
        return False


def _test_url_alias():
    """测试 Url 别名"""
    try:
        elem = Url("https://example.com")
        if not isinstance(elem, URLElement):
            return False
        return True
    except Exception:
        return False


def _test_i18n_context():
    """测试 I18NContext 别名"""
    try:
        from core.builtins.message.elements import I18NContextElement

        elem = I18NContext("test.key", param="value")
        if not isinstance(elem, I18NContextElement):
            return False
        return True
    except Exception:
        return False


@func_case
async def test_message_chain(tester: Tester):
    """core.builtins.message.chain: MessageChain 测试"""
    await tester.test(_test_assign_from_string, "从字符串创建消息链")
    await tester.test(_test_assign_from_none, "从 None 创建空消息链")
    await tester.test(_test_assign_from_element, "从单个元素创建消息链")
    await tester.test(_test_assign_from_list, "从列表创建消息链")
    await tester.test(_test_assign_from_tuple, "从元组创建消息链")
    await tester.test(_test_assign_from_message_chain, "从 MessageChain 创建消息链")
    await tester.test(_test_assign_empty_string, "空字符串处理")
    await tester.test(_test_assign_mixed_list, "混合类型列表")
    await tester.test(_test_to_str, "to_str() 方法")
    await tester.test(_test_to_str_multiple, "多个元素的 to_str()")
    await tester.test(_test_len, "消息链长度")
    await tester.test(_test_len_empty, "空消息链长度")

    return tester


@func_case
async def test_message_elements(tester: Tester):
    """core.builtins.message.elements: 消息元素测试"""
    await tester.test(_test_plain_element_assign, "PlainElement.assign()")
    await tester.test(_test_plain_element_multiple_args, "PlainElement.assign() 多参数")
    await tester.test(_test_plain_element_str, "PlainElement.__str__()")
    await tester.test(_test_plain_element_kecode, "PlainElement.kecode()")
    await tester.test(_test_plain_element_kecode_disable_joke, "PlainElement.kecode() 禁用玩笑")
    await tester.test(_test_url_element_assign, "URLElement.assign()")
    await tester.test(_test_url_element_str, "URLElement.__str__()")

    return tester


@func_case
async def test_message_internal(tester: Tester):
    """core.builtins.message.internal: 内部消息别名测试"""
    await tester.test(_test_plain_alias, "Plain 别名")
    await tester.test(_test_url_alias, "Url 别名")
    await tester.test(_test_i18n_context, "I18NContext 别名")

    return tester


def _test_chain_add():
    """MessageChain: + 运算符"""
    try:
        c1 = MessageChain.assign("Hello")
        c2 = MessageChain.assign("World")
        result = c1 + c2
        if len(result) != 2:
            return False
        if result.to_str() != "Hello\nWorld":
            return False
        return True
    except Exception:
        return False


def _test_chain_iadd():
    """MessageChain: += 运算符"""
    try:
        c1 = MessageChain.assign("Hello")
        c1 += MessageChain.assign("World")
        if len(c1) != 2:
            return False
        return True
    except Exception:
        return False


def _test_chain_radd():
    """MessageChain: list + MessageChain"""
    try:
        elems = [PlainElement.assign("A")]
        chain = MessageChain.assign("B")
        result = elems + chain
        if len(result) != 2:
            return False
        return True
    except Exception:
        return False


def _test_chain_is_safe():
    """MessageChain: is_safe 属性"""
    try:
        chain = MessageChain.assign("Hello World")
        return chain.is_safe is True
    except Exception:
        return False


def _test_chain_append():
    """MessageChain: append 方法"""
    try:
        chain = MessageChain.assign("Hello")
        chain.append(PlainElement.assign(" World"))
        if len(chain) != 2:
            return False
        return True
    except Exception:
        return False


def _test_chain_copy():
    """MessageChain: copy 方法"""
    try:
        chain = MessageChain.assign("Original")
        copy_chain = chain.copy()
        if chain.to_str() != copy_chain.to_str():
            return False
        copy_chain.append(PlainElement.assign(" Modified"))
        if len(chain) != 1:
            return False
        return True
    except Exception:
        return False


def _test_chain_to_str_connector():
    """MessageChain: to_str 自定义连接符"""
    try:
        chain = MessageChain.assign([PlainElement.assign("A"), PlainElement.assign("B")])
        result = chain.to_str(connector=" ")
        return result == "A B"
    except Exception:
        return False


def _test_image_element_assign():
    """ImageElement: assign 本地路径"""
    try:
        elem = ImageElement.assign("/tmp/test.png")
        if elem.path != "/tmp/test.png":
            return False
        if elem.need_get is True:
            return False
        return True
    except Exception:
        return False


def _test_image_element_url():
    """ImageElement: assign URL"""
    try:
        elem = ImageElement.assign("https://example.com/img.png")
        if elem.need_get is not True:
            return False
        return True
    except Exception:
        return False


def _test_voice_element_assign():
    """VoiceElement: assign"""
    try:
        from core.builtins.message.elements import VoiceElement

        elem = VoiceElement.assign("/tmp/audio.mp3")
        if elem.path != "/tmp/audio.mp3":
            return False
        ke = elem.kecode()
        if "voice" not in ke:
            return False
        return True
    except Exception:
        return False


def _test_mention_element_assign():
    """MentionElement: assign"""
    try:
        elem = MentionElement.assign("QQ|123456789")
        if elem.client != "QQ":
            return False
        if elem.id != "123456789":
            return False
        return True
    except Exception:
        return False


def _test_embed_element_assign():
    """EmbedElement: assign"""
    try:
        elem = EmbedElement.assign(title="Test", description="Desc")
        if elem.title != "Test":
            return False
        if elem.description != "Desc":
            return False
        return True
    except Exception:
        return False


@func_case
async def test_message_chain_operations(tester: Tester):
    """MessageChain: 运算符和高级操作测试"""
    await tester.test(_test_chain_add, "MessageChain + 运算符")
    await tester.test(_test_chain_iadd, "MessageChain += 运算符")
    await tester.test(_test_chain_radd, "list + MessageChain 运算符")
    await tester.test(_test_chain_is_safe, "MessageChain is_safe 属性")
    await tester.test(_test_chain_append, "MessageChain append 方法")
    await tester.test(_test_chain_copy, "MessageChain copy 方法")
    await tester.test(_test_chain_to_str_connector, "MessageChain to_str 自定义连接符")
    return tester


@func_case
async def test_message_elements_extended(tester: Tester):
    """消息元素扩展测试: Image/Voice/Mention/Embed"""
    await tester.test(_test_image_element_assign, "ImageElement.assign 本地路径")
    await tester.test(_test_image_element_url, "ImageElement.assign URL")
    await tester.test(_test_voice_element_assign, "VoiceElement.assign")
    await tester.test(_test_mention_element_assign, "MentionElement.assign")
    await tester.test(_test_embed_element_assign, "EmbedElement.assign")
    return tester
