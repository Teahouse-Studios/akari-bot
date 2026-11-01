"""Satori 适配器消息转换单元测试。"""

from satori import element as sat

from bots.satori.utils import (
    build_channel_target_id,
    build_private_target_id,
    build_sender_id,
    convert_chain_to_elements,
    parse_inbound,
    parse_sender_id,
    parse_target_id,
)
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ImageElement, PlainElement
from core.builtins.message.internal import Image, Mention, Plain
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.tester import func_case, Tester


async def _session(**kwargs) -> SessionInfo:
    return await SessionInfo.assign(
        target_id="Satori|Channel|qq|guild|channel",
        target_from="Satori|Channel",
        client_name="Satori",
        sender_id="Satori|User|qq|1",
        features=Features(support_image=True),
        **kwargs,
    )


def _texts(chain: MessageChain) -> list[str]:
    return [element.text for element in chain.values if isinstance(element, PlainElement)]


def _test_parse_text_with_leading_at():
    inbound = parse_inbound('<at id="1"/> ~help', bot_id="1")
    return inbound.at_bot and not inbound.addressed_other and _texts(inbound.messages) == [" ~help"]


def _test_parse_at_other():
    other = parse_inbound('<at id="2"/> ~help', bot_id="1")
    everyone = parse_inbound('<at type="all"/> ~help', bot_id="1")
    return other.addressed_other and not other.at_bot and not everyone.addressed_other


def _test_parse_style_and_break():
    inbound = parse_inbound("<b>粗体</b><br/>下一行", bot_id="1")
    return _texts(inbound.messages) == ["粗体\n下一行"]


def _test_parse_quote_and_image():
    inbound = parse_inbound('<quote id="9"/><img src="https://example.com/a.png"/>', bot_id="1")
    if inbound.reply_id != "9":
        return False
    values = inbound.messages.values
    return len(values) == 1 and isinstance(values[0], ImageElement) and values[0].path == "https://example.com/a.png"


def _test_target_id_roundtrip():
    channel = parse_target_id(build_channel_target_id("qq", "guild", "channel"))
    private = parse_target_id(build_private_target_id("discord", "42"))
    if channel is None or channel.is_private or channel.guild_id != "guild" or channel.raw_id != "channel":
        return False
    if private is None or not private.is_private or private.guild_id is not None or private.raw_id != "42":
        return False
    if parse_sender_id(build_sender_id("qq", "42")) != ("qq", "42"):
        return False
    return parse_target_id("QQ|Group|1") is None and parse_sender_id("QQ|1") is None


async def _test_outbound_at_code():
    session = await _session()
    elements = await convert_chain_to_elements(
        session,
        MessageChain.assign([Plain("你好 <AT:Satori|42> 再见")]),
        bot_ids={"1"},
        upload=lambda element: None,
        quote=False,
    )
    expected = [sat.Text("你好 "), sat.At(id="42"), sat.Text(" 再见")]
    return [type(element) for element in elements] == [type(item) for item in expected] and [
        str(element) for element in elements
    ] == [str(item) for item in expected]


async def _test_outbound_quote_and_mention():
    session = await _session(message_id="7")
    elements = await convert_chain_to_elements(
        session,
        MessageChain.assign([Mention("Satori|42"), Plain("收到")]),
        bot_ids={"1"},
        upload=lambda element: None,
    )
    return (
        len(elements) == 4
        and isinstance(elements[0], sat.Quote)
        and elements[0].id == "7"
        and isinstance(elements[1], sat.At)
        and elements[1].id == "42"
        and isinstance(elements[2], sat.Br)
        and isinstance(elements[3], sat.Text)
        and elements[3].text == "收到"
    )


async def _test_outbound_self_mention_and_image():
    session = await _session()

    async def upload(element):
        return element.path

    elements = await convert_chain_to_elements(
        session,
        MessageChain.assign([Mention("Satori|1"), Image("https://example.com/a.png")]),
        bot_ids={"1"},
        upload=upload,
        quote=False,
    )
    return (
        len(elements) == 3
        and isinstance(elements[0], sat.Text)
        and elements[0].text == " "
        and isinstance(elements[1], sat.Br)
        and isinstance(elements[2], sat.Image)
        and elements[2].src == "https://example.com/a.png"
    )


def _shape(elements):
    return [element.text if isinstance(element, sat.Text) else element.tag for element in elements]


async def _test_outbound_line_breaks():
    session = await _session()

    async def upload(element):
        return element.path

    async def convert(chain):
        return _shape(
            await convert_chain_to_elements(
                session,
                chain,
                bot_ids={"1"},
                upload=upload,
                quote=False,
            )
        )

    separate = await convert(MessageChain.assign([Plain("A"), Plain("B")]))
    blank_line = await convert(MessageChain.assign([Plain("A\n\nB")]))
    trailing_break = await convert(MessageChain.assign([Plain("A\n"), Plain("B")]))
    around_media = await convert(MessageChain.assign([Plain("A"), Image("https://example.com/a.png"), Plain("B")]))
    sections = await convert(MessageChain.assign([Plain("A：\n1"), Plain("B：\n2")]))
    return (
        separate == ["A", "br", "B"]
        and blank_line == ["A", "br", "br", "B"]
        and trailing_break == ["A", "br", "B"]
        and around_media == ["A", "br", "img", "br", "B"]
        and sections == ["A：", "br", "1", "br", "B：", "br", "2"]
    )


@func_case
async def test_satori_inbound(tester: Tester):
    """bots.satori.utils: Satori 入站元素解析测试"""
    await tester.test(_test_parse_text_with_leading_at, "首位提及机器人")
    await tester.test(_test_parse_at_other, "首位提及他人")
    await tester.test(_test_parse_style_and_break, "样式与换行展开")
    await tester.test(_test_parse_quote_and_image, "引用与图片元素")
    return tester


@func_case
async def test_satori_ids(tester: Tester):
    """bots.satori.utils: 场景与用户 ID 编解码测试"""
    await tester.test(_test_target_id_roundtrip, "群聊、私聊与用户 ID 往返")
    return tester


@func_case
async def test_satori_outbound(tester: Tester):
    """bots.satori.utils: Satori 出站元素转换测试"""
    await tester.test(_test_outbound_at_code, "文本内 AT 码转换")
    await tester.test(_test_outbound_quote_and_mention, "引用与提及元素")
    await tester.test(_test_outbound_self_mention_and_image, "跳过自身提及与图片转换")
    await tester.test(_test_outbound_line_breaks, "换行与元素边界保留")
    return tester
