"""Telegram 消息聚合构建器单元测试。"""

import html
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.types import FSInputFile, InputMediaAudio, InputMediaPhoto
from PIL import Image as PILImage

from bots.telegram.message_builder import (
    TelegramAudioOperation,
    TelegramContent,
    TelegramMediaGroupOperation,
    TelegramPhotoOperation,
    TelegramTextOperation,
    build_telegram_operations,
    collect_telegram_content,
    execute_telegram_operations,
    split_telegram_html,
)
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, Button, Image, Mention, Plain, Voice
from core.builtins.session.info import SessionInfo
from core.i18n import Locale
from core.tester import Tester, func_case
from core.utils.image_split import image_split


def _visible(chunks: list[str]) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", "".join(chunks)))


def _test_plain_text_splits_at_limit():
    return split_telegram_html("a" * 11, 10) == ["a" * 10, "a"]


def _test_prefers_newline_boundary():
    return split_telegram_html("12345\n67890", 8) == ["12345", "67890"]


def _test_long_plain_text_uses_lightweight_split_path():
    text = "a" * 100_000
    with patch("bots.telegram.message_builder._HTMLAtomParser", side_effect=AssertionError):
        chunks = split_telegram_html(text, 4096)
    return "".join(chunks) == text and all(len(chunk) <= 4096 for chunk in chunks)


def _test_anchor_is_closed_and_reopened():
    text = '<a href="tg://user?id=1">' + "x" * 20 + "</a>"
    chunks = split_telegram_html(text, 10)
    return (
        chunks
        == [
            '<a href="tg://user?id=1">' + "x" * 10 + "</a>",
            '<a href="tg://user?id=1">' + "x" * 10 + "</a>",
        ]
        and _visible(chunks) == "x" * 20
    )


def _test_entity_is_not_split():
    chunks = split_telegram_html("a&amp;b", 2)
    return chunks == ["a&amp;", "b"] and _visible(chunks) == "a&b"


def _test_self_closing_tag_is_preserved():
    chunks = split_telegram_html("a<br/>b", 10)
    return chunks == ["a<br/>b"]


def _session():
    return SessionInfo(
        target_id="Telegram|Group|1",
        target_from="Telegram|Group",
        client_name="Telegram",
        sender_id="Telegram|User|1",
        sender_from="Telegram|User",
        locale=Locale("zh_cn"),
        support_image=True,
        support_voice=True,
        support_mention=True,
        support_button=True,
    )


async def _test_plain_atcode_is_converted():
    content = await collect_telegram_content(_session(), MessageChain.assign(Plain("hello <AT:Telegram|2>")))
    return content.text == 'hello <a href="tg://user?id=2">@2</a>'


async def _test_plain_allow_parse_skips_atcode():
    content = await collect_telegram_content(
        _session(),
        MessageChain.assign(Plain("hello <AT:Telegram|2>", allow_parse=False)),
    )
    return content.text == "hello &lt;AT:Telegram|2&gt;"


async def _test_plain_html_is_escaped():
    content = await collect_telegram_content(_session(), MessageChain.assign(Plain("参数：<模块名称> & <b>粗体</b>")))
    return content.text == "参数：&lt;模块名称&gt; &amp; &lt;b&gt;粗体&lt;/b&gt;"


async def _test_atcode_keeps_surrounding_text_escaped():
    content = await collect_telegram_content(_session(), MessageChain.assign(Plain("<b>用户</b>：<AT:Telegram|2>")))
    return content.text == '&lt;b&gt;用户&lt;/b&gt;：<a href="tg://user?id=2">@2</a>'


async def _test_action_text_keeps_inline_fallback_and_metadata():
    session = _session()
    session.support_action_text = True
    chain = MessageChain.assign([Plain("提示："), ActionText("~help ", show="帮助"), Plain("参数")])
    content = await collect_telegram_content(session, chain)
    return (
        content.text == "提示：帮助（~help ）参数"
        and len(content.action_texts) == 1
        and content.action_texts[0].text.text == "~help "
    )


async def _test_button_rows_are_collected():
    content = await collect_telegram_content(
        _session(),
        MessageChain.assign([Plain("hello"), Button("Docs", "https://example.com"), Button("Help", "~help")]),
    )
    return content.text == "hello" and [(button.show, button.value) for button in content.button_rows[0].buttons] == [
        ("Docs", "https://example.com"),
        ("Help", "~help"),
    ]


async def _test_button_only_message_gets_placeholder():
    content = await collect_telegram_content(_session(), MessageChain.assign(Button("Help", "~help")))
    return content.text == "\u200b" and content.button_rows[0].buttons[0] == Button("Help", "~help")


async def _test_collects_text_mentions_and_media():
    chain = MessageChain.assign(
        [Plain("hello"), Mention("Telegram|2"), Image("image.png", allow_split=False), Voice("voice.ogg")]
    )
    with (
        patch("bots.telegram.message_builder.FSInputFile", side_effect=lambda path: SimpleNamespace(path=path)),
        patch("core.builtins.message.elements.ImageElement.get", new=AsyncMock(return_value="image.bin")),
    ):
        content = await collect_telegram_content(_session(), chain)
    return (
        content.text == 'hello\n<a href="tg://user?id=2">@2</a>'
        and len(content.images) == 1
        and len(content.audio) == 1
    )


async def _test_image_split_boundaries_have_no_empty_crop():
    expected = {
        1499: [1499],
        1500: [1500],
        1501: [1500, 1],
        3000: [1500, 1500],
    }
    for height, expected_heights in expected.items():
        source = Image(PILImage.new("RGB", (1, height)))
        split = await image_split(source)
        actual_heights = []
        for item in split:
            with PILImage.open(await item.get()) as opened:
                actual_heights.append(opened.height)
        if actual_heights != expected_heights:
            return False
    return True


async def _test_image_allow_split_controls_telegram_splitting():
    split_image = Image("split.png")
    unsplit_image = Image("unsplit.png", allow_split=False)
    split_result = Image("part.png", allow_split=False)
    with (
        patch("bots.telegram.message_builder.image_split", new=AsyncMock(return_value=[split_result])) as split,
        patch("core.builtins.message.elements.ImageElement.get", new=AsyncMock(return_value="image.bin")),
    ):
        content = await collect_telegram_content(
            _session(),
            MessageChain.assign([split_image, unsplit_image]),
        )
    return split.await_count == 1 and split.await_args.args == (split_image,) and len(content.images) == 2


def _test_single_photo_uses_caption():
    content = TelegramContent(text="caption", images=[SimpleNamespace(path="a")])
    operations = build_telegram_operations(content)
    return (
        len(operations) == 1
        and isinstance(operations[0], TelegramPhotoOperation)
        and operations[0].caption == "caption"
    )


def _test_media_groups_and_types():
    photos = [FSInputFile(__file__) for _ in range(11)]
    audio = [FSInputFile(__file__), FSInputFile(__file__)]
    operations = build_telegram_operations(TelegramContent(images=photos, audio=audio))
    return (
        isinstance(operations[0], TelegramMediaGroupOperation)
        and len(operations[0].media) == 10
        and all(isinstance(item, InputMediaPhoto) for item in operations[0].media)
        and isinstance(operations[1], TelegramPhotoOperation)
        and isinstance(operations[2], TelegramMediaGroupOperation)
        and all(isinstance(item, InputMediaAudio) for item in operations[2].media)
    )


def _test_caption_overflow_becomes_text_operation():
    operations = build_telegram_operations(TelegramContent(text="a" * 1025, images=[SimpleNamespace(path="a")]))
    return (
        isinstance(operations[0], TelegramPhotoOperation)
        and _visible([operations[0].caption]) == "a" * 1024
        and isinstance(operations[1], TelegramTextOperation)
        and operations[1].text == "a"
    )


def _test_caption_overflow_repacked_to_4096():
    operations = build_telegram_operations(TelegramContent(text="a" * 5000, images=[SimpleNamespace(path="a")]))
    return (
        len(operations) == 2
        and isinstance(operations[0], TelegramPhotoOperation)
        and len(_visible([operations[0].caption])) == 1024
        and isinstance(operations[1], TelegramTextOperation)
        and len(_visible([operations[1].text])) == 3976
    )


def _test_text_without_media_uses_4096_limit():
    operations = build_telegram_operations(TelegramContent(text="a" * 4097))
    return (
        len(operations) == 2
        and all(isinstance(operation, TelegramTextOperation) for operation in operations)
        and [len(operation.text) for operation in operations] == [4096, 1]
    )


def _test_single_audio_operation():
    operations = build_telegram_operations(TelegramContent(audio=[FSInputFile(__file__)]))
    return len(operations) == 1 and isinstance(operations[0], TelegramAudioOperation)


async def _test_execute_operations_collects_ids_and_reply_once():
    messages = [SimpleNamespace(message_id=1), SimpleNamespace(message_id=2), SimpleNamespace(message_id=3)]
    bot = SimpleNamespace(
        send_media_group=AsyncMock(return_value=messages[:2]),
        send_message=AsyncMock(return_value=messages[2]),
    )
    operations = [
        TelegramMediaGroupOperation(media=[InputMediaPhoto(media="a"), InputMediaPhoto(media="b")]),
        TelegramTextOperation(text="after"),
    ]
    sent = await execute_telegram_operations(bot, 10, operations, reply_to_message_id=99, reply_markup=None)
    return (
        sent == messages
        and bot.send_media_group.await_args.kwargs["reply_to_message_id"] == 99
        and bot.send_message.await_args.kwargs["reply_to_message_id"] is None
    )


async def _test_execute_operations_preserves_messages_before_failure():
    first = SimpleNamespace(message_id=1)
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=[first, RuntimeError("send failed")]))
    operations = [TelegramTextOperation(text="one"), TelegramTextOperation(text="two")]
    try:
        sent = await execute_telegram_operations(bot, 10, operations, reply_to_message_id=None, reply_markup=None)
    except Exception:
        return False
    return sent == [first] and bot.send_message.await_count == 2


async def _test_final_media_group_attaches_markup_by_edit():
    markup = SimpleNamespace()
    messages = [SimpleNamespace(message_id=1), SimpleNamespace(message_id=2, edit_reply_markup=AsyncMock())]
    bot = SimpleNamespace(send_media_group=AsyncMock(return_value=messages))
    operation = TelegramMediaGroupOperation(
        media=[InputMediaPhoto(media="a"), InputMediaPhoto(media="b")],
        attach_markup_after_send=True,
    )
    await execute_telegram_operations(bot, 10, [operation], reply_to_message_id=None, reply_markup=markup)
    return messages[-1].edit_reply_markup.await_args.kwargs["reply_markup"] is markup


@func_case
async def test_telegram_message_builder(tester: Tester):
    """Telegram 消息聚合构建器。"""
    await tester.test(_test_plain_text_splits_at_limit, "纯文本按可见长度拆分")
    await tester.test(_test_prefers_newline_boundary, "优先按换行拆分")
    await tester.test(_test_anchor_is_closed_and_reopened, "跨段标签闭合并重开")
    await tester.test(_test_entity_is_not_split, "HTML entity 不被拆开")
    await tester.test(_test_self_closing_tag_is_preserved, "HTML 自闭合标签不丢失")
    await tester.test(_test_plain_atcode_is_converted, "Plain 中的提及转换为 Telegram 格式")
    await tester.test(_test_plain_allow_parse_skips_atcode, "Plain.allow_parse=False 保留 Telegram 提及文本")
    await tester.test(_test_plain_html_is_escaped, "Plain 中的 HTML 特殊字符被转义")
    await tester.test(_test_atcode_keeps_surrounding_text_escaped, "提及转换不放行周围 HTML")
    await tester.test(_test_action_text_keeps_inline_fallback_and_metadata, "ActionText 保持行内降级并收集交互信息")
    await tester.test(_test_button_rows_are_collected, "ButtonElement 收集按钮行")
    await tester.test(_test_button_only_message_gets_placeholder, "纯按钮消息补充不可见正文")
    await tester.test(_test_collects_text_mentions_and_media, "收集文本、提及与媒体")
    await tester.test(_test_single_photo_uses_caption, "单图片使用 caption")
    await tester.test(_test_media_groups_and_types, "媒体分组与类型隔离")
    await tester.test(_test_caption_overflow_becomes_text_operation, "caption 溢出转普通文本")
    await tester.test(_test_caption_overflow_repacked_to_4096, "caption 剩余文本按 4096 重新打包")
    await tester.test(_test_text_without_media_uses_4096_limit, "纯文本使用 4096 字符限制")
    await tester.test(_test_single_audio_operation, "单音频使用单项操作")
    await tester.test(_test_execute_operations_collects_ids_and_reply_once, "执行操作收集消息且仅首条引用")
    await tester.test(_test_execute_operations_preserves_messages_before_failure, "后续发送失败时保留已发送消息")
    await tester.test(_test_final_media_group_attaches_markup_by_edit, "末尾媒体组通过编辑附加按钮")
    await tester.test(_test_long_plain_text_uses_lightweight_split_path, "长纯文本使用轻量拆分路径")
    await tester.test(_test_image_split_boundaries_have_no_empty_crop, "图片高度边界不生成空裁剪")
    await tester.test(_test_image_allow_split_controls_telegram_splitting, "ImageElement.allow_split 控制拆图")
    return tester
