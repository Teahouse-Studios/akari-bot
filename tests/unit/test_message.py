"""core.builtins.message 消息系统单元测试。"""

from core.builtins.message.mention import wrap_sender_id
from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.elements import (
    PlainElement,
    MarkdownElement,
    URLElement,
    ImageElement,
    MentionElement,
    EmbedElement,
    FormattedTimeElement,
    ButtonElement,
    ButtonRows,
    ButtonFrameElement,
)
from core.builtins.message.internal import (
    Markdown,
    Plain,
    Button,
    ButtonFrame,
)
from core.tester import func_case, Tester


def _test_assign_from_string():
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
    try:
        chain1 = MessageChain.assign("Original")
        chain2 = MessageChain.assign(chain1)
        if chain1 is not chain2:
            return False
        return True
    except Exception:
        return False


def _test_assign_empty_string():
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
    try:
        elems = ["text1", PlainElement.assign("text2")]
        chain = MessageChain.assign(elems)
        if len(chain.values) != 2:
            return False
        return True
    except Exception:
        return False


def _test_to_str():
    try:
        chain = MessageChain.assign("Hello World")
        result = chain.to_str()
        if result != "Hello World":
            return False
        return True
    except Exception:
        return False


def _test_to_str_multiple():
    try:
        chain = MessageChain.assign([PlainElement.assign("Hello "), PlainElement.assign("World")])
        result = chain.to_str()
        if "Hello" not in result or "World" not in result:
            return False
        return True
    except Exception:
        return False


def _test_plain_element_multiple_args():
    try:
        elem = PlainElement.assign("Hello", " ", "World")
        if elem.text != "Hello World":
            return False
        return True
    except Exception:
        return False


def _test_plain_element_kecode():
    try:
        elem = PlainElement.assign("Hello")
        kecode = elem.kecode()
        if "[KE:plain,text=Hello]" != kecode:
            return False
        return True
    except Exception:
        return False


def _test_plain_element_kecode_disable_joke():
    try:
        elem = PlainElement.assign("Hello", disable_joke=True)
        kecode = elem.kecode()
        if "[KE:plain,text=Hello,disable_joke=1]" != kecode:
            return False
        return True
    except Exception:
        return False


def _test_markdown_element_and_plain_conversion():
    source = (
        "# 标题\n\n**粗体**与[链接](https://example.com)\n"
        "- 条目\n| 列一 | 列二 |\n|---|---|\n| 甲 | 乙 |\n```代码\nprint('ok')\n```"
    )
    element = Markdown(source, disable_joke=True)
    plain = element.to_plain()
    return (
        isinstance(element, MarkdownElement)
        and str(element) == source
        and isinstance(plain, PlainElement)
        and not isinstance(plain, MarkdownElement)
        and plain.disable_joke
        and plain.text == "标题\n\n粗体与链接 (https://example.com)\n• 条目\n列一 | 列二\n甲 | 乙\n代码\nprint('ok')"
    )


def _test_markdown_sendable_respects_session_capability():
    from types import SimpleNamespace

    from core.i18n import Locale

    def session(support_markdown):
        return SimpleNamespace(
            support_embed=False,
            support_markdown=support_markdown,
            locale=Locale("zh_cn"),
        )

    chain = MessageChain.assign(Markdown("**粗体**", disable_joke=True))
    supported = chain.as_sendable(session(True)).values[0]
    unsupported = chain.as_sendable(session(False)).values[0]
    disabled = chain.as_sendable(session(True), enable_markdown=False).values[0]
    return (
        isinstance(supported, MarkdownElement)
        and supported.text == "**粗体**"
        and type(unsupported) is PlainElement
        and unsupported.text == "粗体"
        and type(disabled) is PlainElement
        and disabled.text == "粗体"
    )


def _test_markdown_roundtrip():
    raw = "**a,b]c**"
    element = Markdown(raw, disable_joke=True)
    restored_kecode = match_kecode(element.kecode()).values[0]
    restored_chain = MessageChain.from_list(MessageChain.assign(element).to_list()).values[0]
    return (
        isinstance(restored_kecode, MarkdownElement)
        and restored_kecode.text == raw
        and restored_kecode.disable_joke
        and isinstance(restored_chain, MarkdownElement)
        and restored_chain == element
    )


def _test_plain_kecode_roundtrip_separators():
    try:
        for raw in ("a,b c", "见 [1] 条", "x=1,y=2", "100% 完成", "混合 a,b] c=d"):
            elem = PlainElement.assign(raw)
            chain = match_kecode(elem.kecode())
            if len(chain.values) != 1:
                return False
            if chain.values[0].text != raw:
                return False
        return True
    except Exception:
        return False


def _test_plain_kecode_roundtrip_disable_joke():
    try:
        elem = PlainElement.assign("a,b]c", disable_joke=True)
        restored = match_kecode(elem.kecode()).values[0]
        if restored.text != "a,b]c":
            return False
        if restored.disable_joke is not True:
            return False
        return True
    except Exception:
        return False


def _test_plain_allow_parse_roundtrip_and_behavior():
    from types import SimpleNamespace

    from core.i18n import Locale

    try:
        raw = "[KE:mention,userid=QQ|123]"
        element = Plain(raw, allow_parse=False)
        restored_kecode = match_kecode(element.kecode()).values[0]
        restored_chain = MessageChain.from_list(MessageChain.assign(element).to_list()).values[0]
        session = SimpleNamespace(support_embed=False, locale=Locale("zh_cn"))
        parsed = MessageChain.assign(Plain(raw)).as_sendable(session)
        unparsed = MessageChain.assign(element).as_sendable(session)
        markdown_plain = Markdown("**hello**", allow_parse=False).to_plain()
        return (
            restored_kecode.allow_parse is False
            and restored_chain.allow_parse is False
            and parsed.contains(MentionElement)
            and len(unparsed.values) == 1
            and type(unparsed.values[0]) is PlainElement
            and unparsed.values[0].text == raw
            and unparsed.values[0].allow_parse is False
            and markdown_plain.allow_parse is False
        )
    except Exception:
        return False


def _test_formatted_time_kecode_roundtrip():
    try:
        elem = FormattedTimeElement.assign(1234567890.0)
        expected = elem.to_str()
        restored = match_kecode(elem.kecode()).values[0]
        if restored.text != expected:
            return False
        # 逗号后的部分不应丢失
        if "," in expected and restored.text == expected.split(",")[0]:
            return False
        return True
    except Exception:
        return False


def _test_url_kecode_roundtrip():
    try:
        raw = "https://example.com/a?x=1,2&y=3"
        elem = URLElement.assign(raw)
        restored = match_kecode(elem.kecode()).values[0]
        if str(restored) != raw:
            return False
        return True
    except Exception:
        return False


def _test_url_kecode_missing_text():
    try:
        chain = match_kecode("[KE:url]")
        for value in chain.values:
            if isinstance(value, URLElement):
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

    return tester


@func_case
async def test_message_elements(tester: Tester):
    """core.builtins.message.elements: 消息元素测试"""
    await tester.test(_test_plain_element_multiple_args, "PlainElement.assign() 多参数")
    await tester.test(_test_plain_element_kecode, "PlainElement.kecode()")
    await tester.test(_test_plain_element_kecode_disable_joke, "PlainElement.kecode() 禁用玩笑")
    await tester.test(_test_markdown_element_and_plain_conversion, "MarkdownElement 普通文本转换")
    await tester.test(_test_markdown_sendable_respects_session_capability, "MarkdownElement 平台能力降级")

    return tester


@func_case
async def test_kecode_roundtrip(tester: Tester):
    """core.builtins.message: KE 码转义往返测试"""
    await tester.test(_test_plain_kecode_roundtrip_separators, "纯文本含分隔符往返测试")
    await tester.test(_test_plain_kecode_roundtrip_disable_joke, "含分隔符时 disable_joke 往返测试")
    await tester.test(_test_plain_allow_parse_roundtrip_and_behavior, "PlainElement.allow_parse 往返与解析控制")
    await tester.test(_test_markdown_roundtrip, "MarkdownElement KE 码与结构化往返测试")
    await tester.test(_test_formatted_time_kecode_roundtrip, "格式化时间往返测试")
    await tester.test(_test_url_kecode_roundtrip, "URL 含逗号往返测试")
    await tester.test(_test_url_kecode_missing_text, "url 缺少 text 参数测试")

    return tester


def _test_chain_add():
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
    try:
        c1 = MessageChain.assign("Hello")
        c1 += MessageChain.assign("World")
        if len(c1) != 2:
            return False
        return True
    except Exception:
        return False


def _test_chain_radd():
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
    try:
        chain = MessageChain.assign("Hello World")
        return chain.is_safe is True
    except Exception:
        return False


def _test_chain_copy():
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
    try:
        chain = MessageChain.assign([PlainElement.assign("A"), PlainElement.assign("B")])
        result = chain.to_str(connector=" ")
        return result == "A B"
    except Exception:
        return False


def _test_image_element_assign():
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
    try:
        elem = ImageElement.assign("https://example.com/img.png")
        if elem.need_get is not True:
            return False
        return True
    except Exception:
        return False


def _test_image_element_max_h_roundtrip():
    try:
        elem = ImageElement.assign("https://example.com/img.png", max_h=512)
        restored_kecode = match_kecode(elem.kecode()).values[0]
        restored_chain = MessageChain.from_list(MessageChain.assign(elem).to_list()).values[0]
        return elem.max_h == 512 and restored_kecode.max_h == 512 and restored_chain.max_h == 512
    except Exception:
        return False


def _test_image_element_allow_split_roundtrip():
    try:
        elem = ImageElement.assign("https://example.com/img.png", allow_split=False)
        restored_kecode = match_kecode(elem.kecode()).values[0]
        restored_chain = MessageChain.from_list(MessageChain.assign(elem).to_list()).values[0]
        default_kecode = match_kecode(ImageElement.assign("https://example.com/default.png").kecode()).values[0]
        return (
            elem.allow_split is False
            and restored_kecode.allow_split is False
            and restored_chain.allow_split is False
            and default_kecode.allow_split is True
        )
    except Exception:
        return False


def _test_image_element_preserves_pil_format():
    try:
        from io import BytesIO

        from PIL import Image as PILImage

        buffer = BytesIO()
        PILImage.new("RGB", (1, 1), "red").save(buffer, format="JPEG")
        buffer.seek(0)
        with PILImage.open(buffer) as image:
            elem = ImageElement.assign(image)

        with PILImage.open(elem.path) as saved:
            jpeg_ok = elem.path.endswith(".jpg") and saved.format == "JPEG"

        generated = ImageElement.assign(PILImage.new("RGBA", (1, 1)))
        with PILImage.open(generated.path) as saved:
            return jpeg_ok and generated.path.endswith(".png") and saved.format == "PNG"
    except Exception:
        return False


def _test_image_element_preserves_base64_format():
    try:
        import base64
        from io import BytesIO
        from pathlib import Path

        from PIL import Image as PILImage

        buffer = BytesIO()
        PILImage.new("RGB", (1, 1), "red").save(buffer, format="JPEG")
        raw = buffer.getvalue()
        encoded = base64.b64encode(raw).decode()

        for source in (f"base64://{encoded}", f"data:image/jpeg;base64,{encoded}"):
            elem = ImageElement.assign(source)
            if not elem.path.endswith(".jpg"):
                return False
            if Path(elem.path).read_bytes() != raw:
                return False
            with PILImage.open(elem.path) as saved:
                if saved.format != "JPEG":
                    return False
        return True
    except Exception:
        return False


def _test_audio_element_assign():
    try:
        from core.builtins.message.elements import AudioElement

        elem = AudioElement.assign("/tmp/audio.mp3")
        if elem.path != "/tmp/audio.mp3":
            return False
        ke = elem.kecode()
        if "audio" not in ke:
            return False
        return True
    except Exception:
        return False


def _test_video_element_assign():
    try:
        from core.builtins.message.elements import VideoElement

        elem = VideoElement.assign("/tmp/video.mp4")
        if elem.path != "/tmp/video.mp4":
            return False
        ke = elem.kecode()
        if "video" not in ke:
            return False
        return True
    except Exception:
        return False


def _test_mention_element_assign():
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
    try:
        elem = EmbedElement.assign(title="Test", description="Desc")
        if elem.title != "Test":
            return False
        if elem.description != "Desc":
            return False
        return True
    except Exception:
        return False


def _test_button_element_roundtrip():
    try:
        button = Button("帮助", "~help", reply_id="callback-123")
        frame = ButtonFrame(
            [
                ButtonRows.assign([Button("文档", "https://example.com"), button]),
                ButtonRows.assign([Button("设置", "~setup")]),
            ]
        )
        if not isinstance(button, ButtonElement) or not isinstance(frame, ButtonFrameElement):
            return False
        restored_kecode = match_kecode(frame.kecode()).values[0]
        restored_chain = MessageChain.from_list(MessageChain.assign(frame).to_list()).values[0]
        return (
            isinstance(restored_kecode, ButtonFrameElement)
            and restored_kecode == frame
            and isinstance(restored_chain, ButtonFrameElement)
            and restored_chain == frame
            and match_kecode(button.kecode()).values[0] == button
            and button.payload.to_data() == "<q:callback-123>~help"
        )
    except Exception:
        return False


def _test_button_element_follows_platform_capability():
    try:
        from types import SimpleNamespace

        from core.i18n import Locale

        chain = MessageChain.assign([Plain("提示"), Button("帮助", "~help")])
        supported = SimpleNamespace(
            support_embed=True,
            support_button=True,
            support_action_text=False,
            use_url_manager=False,
            use_url_md_format=False,
            locale=Locale("zh_cn"),
        )
        unsupported = SimpleNamespace(
            support_embed=True,
            support_button=False,
            support_action_text=False,
            use_url_manager=False,
            use_url_md_format=False,
            locale=Locale("zh_cn"),
        )
        return chain.as_sendable(supported).contains(ButtonFrameElement) and not chain.as_sendable(
            unsupported
        ).contains(ButtonFrameElement)
    except Exception:
        return False


def _test_standalone_buttons_are_auto_arranged():
    try:
        buttons = [Button(str(index), f"~button {index}") for index in range(55)]
        sendable = MessageChain.assign(buttons).as_sendable()
        frames = [element for element in sendable if isinstance(element, ButtonFrameElement)]
        return (
            len(frames) == 1
            and [len(row.buttons) for row in frames[0].rows] == [10, 10, 10, 10, 10]
            and frames[0].rows[-1].buttons[-1].show == "49"
        )
    except Exception:
        return False


def _test_wrap_sender_id_wraps_sender_id():
    try:
        if wrap_sender_id(r"TEST|0 说 hi", "TEST") != "<AT:TEST|0> 说 hi":
            return False
        return wrap_sender_id("<AT:TEST|0> hi", "TEST") == "<AT:TEST|0> hi"
    except Exception:
        return False


def _test_wrap_sender_id_preserves_backslashes():
    cases = (
        (r"a\b", r"a\b"),
        (r"a\\b", r"a\\b"),
        (r"\d+", r"\d+"),
        (r"C:\\Users", r"C:\\Users"),
        (r"C:\\Users TEST|0", r"C:\\Users <AT:TEST|0>"),
    )
    try:
        return all(wrap_sender_id(text, "TEST") == expected for text, expected in cases)
    except Exception:
        return False


@func_case
async def test_message_chain_operations(tester: Tester):
    """MessageChain: 运算符和高级操作测试"""
    await tester.test(_test_chain_add, "MessageChain + 运算符")
    await tester.test(_test_chain_iadd, "MessageChain += 运算符")
    await tester.test(_test_chain_radd, "list + MessageChain 运算符")
    await tester.test(_test_chain_is_safe, "MessageChain is_safe 属性")
    await tester.test(_test_chain_copy, "MessageChain copy 方法")
    await tester.test(_test_chain_to_str_connector, "MessageChain to_str 自定义连接符")
    await tester.test(_test_wrap_sender_id_wraps_sender_id, "wrap_sender_id 包装发送者 ID")
    await tester.test(_test_wrap_sender_id_preserves_backslashes, "wrap_sender_id 保留反斜杠")
    return tester


@func_case
async def test_message_elements_extended(tester: Tester):
    """消息元素扩展测试: Image/Audio/Mention/Embed"""
    await tester.test(_test_image_element_assign, "ImageElement.assign 本地路径")
    await tester.test(_test_image_element_url, "ImageElement.assign URL")
    await tester.test(_test_image_element_max_h_roundtrip, "ImageElement.max_h 序列化往返")
    await tester.test(_test_image_element_allow_split_roundtrip, "ImageElement.allow_split 序列化往返")
    await tester.test(_test_image_element_preserves_pil_format, "ImageElement.assign 保留 PIL 格式")
    await tester.test(_test_image_element_preserves_base64_format, "ImageElement.assign 保留 Base64 格式")
    await tester.test(_test_audio_element_assign, "AudioElement.assign")
    await tester.test(_test_mention_element_assign, "MentionElement.assign")
    await tester.test(_test_embed_element_assign, "EmbedElement.assign")
    await tester.test(_test_button_element_roundtrip, "Button 与 ButtonFrame 构造及序列化往返")
    await tester.test(_test_button_element_follows_platform_capability, "ButtonFrame 按平台能力保留或忽略")
    await tester.test(_test_standalone_buttons_are_auto_arranged, "单个 Button 自动按 10 × 5 规整")
    return tester
