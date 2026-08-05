"""Discord 消息聚合构建器单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, Embed, Image, Mention, Plain, Voice
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import Tester, func_case
from bots.discord.message_builder import (
    DiscordPayload,
    build_discord_payloads,
    execute_discord_payloads,
    split_discord_text,
)


def _session():
    return SessionInfo(
        target_id="Discord|Channel|1",
        target_from="Discord|Channel",
        client_name="Discord",
        sender_id="Discord|Client|1",
        sender_from="Discord|Client",
        locale=Locale("zh_cn"),
        support_image=True,
        support_voice=True,
        support_mention=True,
        support_embed=True,
    )


def _test_text_splits_at_2000():
    text = "a" * 2001
    chunks = split_discord_text(text)
    return [len(chunk) for chunk in chunks] == [2000, 1] and "".join(chunks) == text


def _test_text_prefers_newline():
    chunks = split_discord_text("a" * 1500 + "\n" + "b" * 600)
    return chunks == ["a" * 1500, "b" * 600]


async def _test_plain_atcode_is_converted():
    payloads = await build_discord_payloads(_session(), MessageChain.assign(Plain("hello <AT:Discord|2>")))
    return payloads[0].content == "hello <@2>"


async def _test_action_text_keeps_inline_fallback_and_metadata():
    session = _session()
    session.support_action_text = True
    chain = MessageChain.assign([Plain("提示："), ActionText("~help ", show="帮助"), Plain("参数")])
    payloads = await build_discord_payloads(session, chain)
    return (
        payloads[0].content == "提示：帮助（~help ）参数"
        and len(payloads[-1].action_texts) == 1
        and payloads[-1].action_texts[0].text.text == "~help "
    )


async def _test_mixed_elements_fit_one_payload():
    chain = MessageChain.assign(
        [Plain("hello"), Mention("Discord|2"), Image("image.png"), Voice("voice.ogg"), Embed(title="card")]
    )
    fake_file = SimpleNamespace(filename="direct.bin")
    fake_embed = SimpleNamespace()
    with (
        patch("bots.discord.message_builder.discord.File", return_value=fake_file),
        patch("bots.discord.message_builder.convert_embed", new=AsyncMock(return_value=(fake_embed, []))),
        patch("core.builtins.message.elements.ImageElement.get", new=AsyncMock(return_value=b"image")),
    ):
        payloads = await build_discord_payloads(_session(), chain)
    payload = payloads[0]
    return (
        len(payloads) == 1
        and payload.content == "hello\n<@2>"
        and len(payload.files) == 2
        and payload.embeds == [fake_embed]
    )


async def _test_file_limit_creates_second_payload():
    chain = MessageChain.assign([Image(f"{index}.png") for index in range(11)])
    with (
        patch("bots.discord.message_builder.discord.File", side_effect=lambda *_args, **kwargs: kwargs),
        patch("core.builtins.message.elements.ImageElement.get", new=AsyncMock(return_value=b"image")),
    ):
        payloads = await build_discord_payloads(_session(), chain)
    return [len(payload.files) for payload in payloads] == [10, 1]


async def _test_embed_limit_creates_second_payload():
    chain = MessageChain.assign([Embed(title=str(index)) for index in range(11)])
    with patch(
        "bots.discord.message_builder.convert_embed",
        new=AsyncMock(side_effect=[(SimpleNamespace(index=index), []) for index in range(11)]),
    ):
        payloads = await build_discord_payloads(_session(), chain)
    return [len(payload.embeds) for payload in payloads] == [10, 1]


async def _test_embed_attachment_stays_with_embed():
    chain = MessageChain.assign([Image(f"{index}.png") for index in range(10)] + [Embed(title="card")])
    embed = SimpleNamespace()
    embed_file = SimpleNamespace(filename="embed-image.png")
    with (
        patch("bots.discord.message_builder.discord.File", side_effect=lambda *_args, **kwargs: kwargs),
        patch("core.builtins.message.elements.ImageElement.get", new=AsyncMock(return_value=b"image")),
        patch("bots.discord.message_builder.convert_embed", new=AsyncMock(return_value=(embed, [embed_file]))),
    ):
        payloads = await build_discord_payloads(_session(), chain)
    embed_payload = next(payload for payload in payloads if embed in payload.embeds)
    return embed_file in embed_payload.files and len(embed_payload.files) <= 10


async def _test_execute_uses_reference_first_and_view_last():
    sent = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    channel = SimpleNamespace(send=AsyncMock(side_effect=sent))
    reference = SimpleNamespace()
    view = SimpleNamespace()
    payloads = [DiscordPayload(content="one"), DiscordPayload(content="two")]
    messages = await execute_discord_payloads(channel, payloads, reference=reference, view=view)
    first, second = channel.send.await_args_list
    return (
        messages == sent
        and first.kwargs["reference"] is reference
        and first.kwargs["view"] is None
        and second.kwargs["reference"] is None
        and second.kwargs["view"] is view
        and first.kwargs["content"] == "one"
        and second.kwargs["content"] == "two"
    )


def _test_interaction_reference_uses_component_message():
    from bots.discord.context import resolve_discord_reference

    message = SimpleNamespace(id=1)
    interaction = SimpleNamespace(message=message)
    return resolve_discord_reference(interaction, quote=True) is message


@func_case
async def test_discord_message_builder(tester: Tester):
    """Discord 消息聚合构建器。"""
    await tester.test(_test_text_splits_at_2000, "文本按 2000 字符拆分")
    await tester.test(_test_text_prefers_newline, "文本优先在换行处分段")
    await tester.test(_test_plain_atcode_is_converted, "Plain 中的提及转换为 Discord 格式")
    await tester.test(_test_action_text_keeps_inline_fallback_and_metadata, "ActionText 保持行内降级并收集交互信息")
    await tester.test(_test_mixed_elements_fit_one_payload, "混合元素合并为一个负载")
    await tester.test(_test_file_limit_creates_second_payload, "附件超过 10 个时拆包")
    await tester.test(_test_embed_limit_creates_second_payload, "Embed 超过 10 个时拆包")
    await tester.test(_test_embed_attachment_stays_with_embed, "Embed 附件与 Embed 保持同包")
    await tester.test(_test_execute_uses_reference_first_and_view_last, "引用仅首条且按钮仅末条")
    await tester.test(_test_interaction_reference_uses_component_message, "Interaction 引用原按钮消息")
    return tester
