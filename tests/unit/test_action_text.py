"""ActionText 消息元素单元测试 - 构造、内层解析与纯文本降级。"""

from urllib.parse import quote

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.elements import (
    ActionTextElement,
    I18NContextElement,
    PlainElement,
    RawElement,
)
from core.builtins.message.internal import ActionText, I18NContext, Plain, Raw
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.tester import func_case, Tester


async def _session(target_suffix: str, support_action_text: bool):
    return await SessionInfo.assign(
        target_id=f"TEST|Group|{target_suffix}",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(support_action_text=support_action_text),
    )


def _test_assign_from_string():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒")
        if not isinstance(elem.text, PlainElement):
            return False
        if elem.text.text != "~wiki 沙盒":
            return False
        if elem.show is not None:
            return False
        if elem.reference is not False:
            return False
        return True
    except Exception:
        return False


def _test_assign_from_elements():
    try:
        elem = ActionTextElement.assign(
            Plain("~wiki 沙盒"),
            show=I18NContext("wiki.message.sandbox"),
            reference=True,
        )
        if not isinstance(elem.text, PlainElement):
            return False
        if not isinstance(elem.show, I18NContextElement):
            return False
        if elem.show.key != "wiki.message.sandbox":
            return False
        if elem.reference is not True:
            return False
        return True
    except Exception:
        return False


def _test_alias_available():
    try:
        elem = ActionText("~wiki 沙盒", show="沙盒")
        if not isinstance(elem, ActionTextElement):
            return False
        if elem.text.text != "~wiki 沙盒":
            return False
        if elem.show.text != "沙盒":
            return False
        return True
    except Exception:
        return False


def _test_resolve_without_session():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒", show="沙盒")
        resolved = elem.resolve(None)
        if resolved.text.text != "~wiki 沙盒":
            return False
        if resolved.show.text != "沙盒":
            return False
        # 幂等：已解析的元素再解析一次不应改变
        again = resolved.resolve(None)
        if again.text.text != "~wiki 沙盒":
            return False
        return True
    except Exception:
        return False


def _test_to_plain_with_show():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒", show="沙盒")
        plain = elem.to_plain(None)
        if not isinstance(plain, PlainElement):
            return False
        # 无会话时退回半角括号
        if plain.text != "沙盒 (~wiki 沙盒)":
            return False
        return True
    except Exception:
        return False


def _test_to_plain_without_show():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒")
        plain = elem.to_plain(None)
        if plain.text != "~wiki 沙盒":
            return False
        return True
    except Exception:
        return False


def _test_to_plain_no_truncation():
    try:
        long_text = "~wiki " + "长" * 200
        elem = ActionTextElement.assign(long_text)
        plain = elem.to_plain(None)
        if plain.text != long_text:
            return False
        return True
    except Exception:
        return False


def _test_in_message_element_union():
    try:
        from core.builtins.types import MessageElement

        elem = ActionTextElement.assign("~wiki 沙盒")
        return isinstance(elem, MessageElement)
    except Exception:
        return False


def _test_kecode_format():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒", show="沙盒", reference=True)
        code = elem.kecode()
        expected = f"[KE:action_text,text={quote('~wiki 沙盒', safe='')},show={quote('沙盒', safe='')},reference=1]"
        return code == expected
    except Exception:
        return False


def _test_kecode_omits_empty_show():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒")
        code = elem.kecode()
        if "show=" in code:
            return False
        if "reference=0" not in code:
            return False
        return True
    except Exception:
        return False


def _test_kecode_roundtrip_special_chars():
    try:
        raw = "~echo a,b]c=d e[KE:plain,text=x]"
        elem = ActionTextElement.assign(raw, show="标签,带]符号")
        chain = match_kecode(elem.kecode())
        if len(chain.values) != 1:
            return False
        restored = chain.values[0]
        if not isinstance(restored, ActionTextElement):
            return False
        if restored.text.text != raw:
            return False
        if restored.show.text != "标签,带]符号":
            return False
        return True
    except Exception:
        return False


def _test_kecode_roundtrip_reference():
    try:
        for flag in (True, False):
            elem = ActionTextElement.assign("~wiki 沙盒", reference=flag)
            restored = match_kecode(elem.kecode()).values[0]
            if restored.reference is not flag:
                return False
        return True
    except Exception:
        return False


def _test_kecode_inline_with_text():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒", show="沙盒")
        chain = match_kecode(f"想了解更多请点击 {elem.kecode()}")
        if len(chain.values) != 2:
            return False
        if not isinstance(chain.values[0], PlainElement):
            return False
        if chain.values[0].text != "想了解更多请点击 ":
            return False
        if not isinstance(chain.values[1], ActionTextElement):
            return False
        return True
    except Exception:
        return False


def _test_kecode_str_equals_kecode():
    try:
        elem = ActionTextElement.assign("~wiki 沙盒")
        return str(elem) == elem.kecode()
    except Exception:
        return False


async def _test_kept_when_supported():
    try:
        session_info = await _session("at_keep", True)
        chain = MessageChain.assign([Plain("提示"), ActionText("~wiki 沙盒", show="沙盒")])
        sendable = chain.as_sendable(session_info)
        if len(sendable.values) != 2:
            return False
        if not isinstance(sendable.values[1], ActionTextElement):
            return False
        # 内层已解析为纯文本元素
        if not isinstance(sendable.values[1].text, PlainElement):
            return False
        return True
    except Exception:
        return False


async def _test_degraded_when_unsupported():
    try:
        session_info = await _session("at_degrade", False)
        chain = MessageChain.assign([Plain("提示："), ActionText("~wiki 沙盒", show="沙盒")])
        sendable = chain.as_sendable(session_info)
        if len(sendable.values) != 1:
            return False
        merged = sendable.values[0]
        if not isinstance(merged, PlainElement):
            return False
        expected_brackets = session_info.locale.t("message.brackets", msg="~wiki 沙盒")
        if merged.text != f"提示：沙盒{expected_brackets}":
            return False
        return True
    except Exception:
        return False


async def _test_degraded_creates_element_when_first():
    try:
        session_info = await _session("at_first", False)
        chain = MessageChain.assign([ActionText("~wiki 沙盒")])
        sendable = chain.as_sendable(session_info)
        if len(sendable.values) != 1:
            return False
        if not isinstance(sendable.values[0], PlainElement):
            return False
        if sendable.values[0].text != "~wiki 沙盒":
            return False
        return True
    except Exception:
        return False


async def _test_degraded_when_markdown_disabled():
    try:
        session_info = await _session("at_nomd", True)
        chain = MessageChain.assign([ActionText("~wiki 沙盒")])
        sendable = chain.as_sendable(session_info, enable_markdown=False)
        if not isinstance(sendable.values[0], PlainElement):
            return False
        return True
    except Exception:
        return False


async def _test_degraded_when_text_empty():
    try:
        session_info = await _session("at_empty", True)
        chain = MessageChain.assign([ActionText("")])
        sendable = chain.as_sendable(session_info)
        for value in sendable.values:
            if isinstance(value, ActionTextElement):
                return False
        return True
    except Exception:
        return False


async def _test_i18n_inner_resolved():
    try:
        session_info = await _session("at_i18n", True)
        chain = MessageChain.assign([ActionText(I18NContext("message.yes"))])
        sendable = chain.as_sendable(session_info)
        elem = sendable.values[0]
        if not isinstance(elem, ActionTextElement):
            return False
        if elem.text.text != session_info.locale.t("message.yes"):
            return False
        return True
    except Exception:
        return False


async def _test_inline_in_i18n_kwargs_supported():
    try:
        session_info = await _session("at_inline_keep", True)
        # message.brackets 的值为「（${msg}）」，借它构造一个前后都有文本的现成句子
        chain = MessageChain.assign([I18NContext("message.brackets", msg=ActionText("~wiki 沙盒", show="沙盒"))])
        sendable = chain.as_sendable(session_info)
        if not any(isinstance(v, ActionTextElement) for v in sendable.values):
            return False
        # 元素前后的括号应作为纯文本保留
        if not any(isinstance(v, PlainElement) for v in sendable.values):
            return False
        return True
    except Exception:
        return False


async def _test_i18n_message_chain_structured_roundtrip():
    try:
        session_info = await _session("i18n_structured_chain", True)
        chain = MessageChain.assign([I18NContext("message.brackets", msg=MessageChain.assign(Raw("<raw,data=1]")))])
        sendable = chain.as_sendable(session_info)
        raw = next((value for value in sendable.values if isinstance(value, RawElement)), None)
        if raw is None or raw.value != "<raw,data=1]":
            return False
        plain_text = "".join(value.text for value in sendable.values if isinstance(value, PlainElement))
        if plain_text != "（）":
            return False
        return True
    except Exception:
        return False


async def _test_inline_degraded_merges_into_one_element():
    try:
        session_info = await _session("at_inline_degrade", False)
        chain = MessageChain.assign([I18NContext("message.brackets", msg=ActionText("~wiki 沙盒", show="沙盒"))])
        sendable = chain.as_sendable(session_info)
        if len(sendable.values) != 1:
            return False
        merged = sendable.values[0]
        if not isinstance(merged, PlainElement):
            return False
        if "~wiki 沙盒" not in merged.text:
            return False
        if "沙盒" not in merged.text:
            return False
        return True
    except Exception:
        return False


async def _test_inline_trailing_text_follows_element():
    try:
        session_info = await _session("at_inline_order", True)
        chain = MessageChain.assign([I18NContext("message.brackets", msg=ActionText("~wiki 沙盒"))])
        sendable = chain.as_sendable(session_info)
        kinds = [type(v).__name__ for v in sendable.values]
        if "ActionTextElement" not in kinds:
            return False
        # 指令操作之后应还有收尾的纯文本
        if kinds.index("ActionTextElement") == len(kinds) - 1:
            return False
        return True
    except Exception:
        return False


async def _test_plain_kecode_roundtrip_not_merged():
    try:
        session_info = await _session("at_plain_roundtrip", False)
        code = MessageChain.assign([Plain("a"), Plain("b")]).to_kecode()
        sendable = MessageChain.assign(code).as_sendable(session_info)
        if len(sendable.values) != 2:
            return False
        if sendable.values[0].text != "a":
            return False
        if sendable.values[1].text != "b":
            return False
        return True
    except Exception:
        return False


async def _test_inline_i18n_inner_translated():
    try:
        session_info = await _session("at_inline_i18n", True)
        chain = MessageChain.assign([I18NContext("message.brackets", msg=ActionText(I18NContext("message.yes")))])
        sendable = chain.as_sendable(session_info)
        for value in sendable.values:
            if isinstance(value, ActionTextElement):
                if value.text.text != session_info.locale.t("message.yes"):
                    return False
                return True
        return False
    except Exception:
        return False


def _test_serialize_roundtrip_plain_inner():
    try:
        from core.builtins.converter import converter
        from core.builtins.types import MessageElement

        elem = ActionTextElement.assign("~wiki 沙盒", show="沙盒", reference=True)
        data = converter.unstructure(elem, MessageElement)
        if data.get("_type") != "ActionTextElement":
            return False
        restored = converter.structure(data, MessageElement)
        if not isinstance(restored, ActionTextElement):
            return False
        if restored.text.text != "~wiki 沙盒":
            return False
        if restored.show.text != "沙盒":
            return False
        if restored.reference is not True:
            return False
        return True
    except Exception:
        return False


def _test_serialize_roundtrip_i18n_inner():
    try:
        from core.builtins.converter import converter
        from core.builtins.types import MessageElement

        elem = ActionTextElement.assign(
            I18NContext("wiki.message.query", page="沙盒"),
            show=I18NContext("wiki.message.label"),
        )
        restored = converter.structure(converter.unstructure(elem, MessageElement), MessageElement)
        if not isinstance(restored.text, I18NContextElement):
            return False
        if restored.text.key != "wiki.message.query":
            return False
        if restored.text.kwargs.get("page") != "沙盒":
            return False
        if not isinstance(restored.show, I18NContextElement):
            return False
        if restored.show.key != "wiki.message.label":
            return False
        return True
    except Exception:
        return False


def _test_serialize_roundtrip_no_show():
    try:
        from core.builtins.converter import converter
        from core.builtins.types import MessageElement

        elem = ActionTextElement.assign("~wiki 沙盒")
        restored = converter.structure(converter.unstructure(elem, MessageElement), MessageElement)
        if restored.show is not None:
            return False
        if restored.reference is not False:
            return False
        return True
    except Exception:
        return False


def _test_serialize_in_message_chain():
    try:
        elem = ActionTextElement.assign(I18NContext("message.yes"), show="标签")
        chain = MessageChain.assign([Plain("提示"), elem])
        restored = MessageChain.from_list(chain.to_list())
        if len(restored.values) != 2:
            return False
        if not isinstance(restored.values[1], ActionTextElement):
            return False
        if not isinstance(restored.values[1].text, I18NContextElement):
            return False
        if restored.values[1].show.text != "标签":
            return False
        return True
    except Exception:
        return False


def _test_to_plain_show_suppressed():
    try:
        elem = ActionTextElement.assign("~bind token ABC", show="点击可添加到输入框", show_on_fallback=False)
        plain = elem.to_plain(None)
        if plain.text != "~bind token ABC":
            return False
        # show 本身仍保留，供支持的平台渲染
        if elem.show.text != "点击可添加到输入框":
            return False
        return True
    except Exception:
        return False


def _test_kecode_roundtrip_show_on_fallback():
    try:
        elem = ActionTextElement.assign("~bind token ABC", show="点击填入", show_on_fallback=False)
        code = elem.kecode()
        if "show_on_fallback=0" not in code:
            return False
        restored = match_kecode(code).values[0]
        if restored.show_on_fallback is not False:
            return False
        if restored.to_plain(None).text != "~bind token ABC":
            return False
        # 默认值不写入 KE 码，还原后仍为 True
        plain_elem = ActionTextElement.assign("~wiki 沙盒", show="沙盒")
        if "show_on_fallback" in plain_elem.kecode():
            return False
        if match_kecode(plain_elem.kecode()).values[0].show_on_fallback is not True:
            return False
        return True
    except Exception:
        return False


async def _test_degraded_suppresses_show():
    try:
        session_info = await _session("at_suppress", False)
        chain = MessageChain.assign(
            [
                ActionText(
                    "~bind token ABC",
                    show=I18NContext("message.action_text.hint", cmd="~bind token ABC"),
                    show_on_fallback=False,
                )
            ]
        )
        sendable = chain.as_sendable(session_info)
        text = "".join(v.text for v in sendable.values if isinstance(v, PlainElement))
        if text != "~bind token ABC":
            return False
        return True
    except Exception:
        return False


def _test_kecode_roundtrip_quote_on_fallback():
    try:
        elem = ActionTextElement.assign("~bind token ABC", quote_on_fallback=True)
        code = elem.kecode()
        if "quote_on_fallback=1" not in code:
            return False
        restored = match_kecode(code).values[0]
        if restored.quote_on_fallback is not True:
            return False
        # 无会话时退回半角引号
        if restored.to_plain(None).text != '"~bind token ABC"':
            return False
        # 默认值不写入 KE 码
        if "quote_on_fallback" in ActionTextElement.assign("~wiki 沙盒").kecode():
            return False
        return True
    except Exception:
        return False


async def _test_degraded_adds_quotes():
    try:
        session_info = await _session("at_quote", False)
        chain = MessageChain.assign(
            [
                ActionText(
                    "~bind token ABC",
                    show=I18NContext("message.action_text.hint", cmd="~bind token ABC"),
                    show_on_fallback=False,
                    quote_on_fallback=True,
                )
            ]
        )
        sendable = chain.as_sendable(session_info)
        text = "".join(v.text for v in sendable.values if isinstance(v, PlainElement))
        expected = session_info.locale.t("message.quotes", msg="~bind token ABC")
        if text != expected:
            return False

        # 支持的平台上元素得以保留，引号不参与其中
        kept = MessageChain.assign([ActionText("~bind token ABC", quote_on_fallback=True)]).as_sendable(
            await _session("at_quote_keep", True)
        )
        if not isinstance(kept.values[0], ActionTextElement):
            return False
        if kept.values[0].text.text != "~bind token ABC":
            return False
        return True
    except Exception:
        return False


@func_case
async def test_action_text_element(tester: Tester):
    """core.builtins.message.elements: ActionTextElement 构造与降级测试"""
    await tester.test(_test_assign_from_string, "字符串入参包装测试")
    await tester.test(_test_assign_from_elements, "元素入参保留测试")
    await tester.test(_test_alias_available, "对外别名测试")
    await tester.test(_test_resolve_without_session, "无会话 resolve() 恒等与幂等测试")
    await tester.test(_test_to_plain_with_show, "带 show 降级文案测试")
    await tester.test(_test_to_plain_without_show, "无 show 降级文案测试")
    await tester.test(_test_to_plain_show_suppressed, "降级略去交互提示测试")
    await tester.test(_test_to_plain_no_truncation, "降级不截断测试")
    await tester.test(_test_in_message_element_union, "MessageElement 联合类型测试")

    return tester


@func_case
async def test_action_text_kecode(tester: Tester):
    """core.builtins.message: ActionTextElement KE 码往返测试"""
    await tester.test(_test_kecode_format, "KE 码格式测试")
    await tester.test(_test_kecode_omits_empty_show, "无 show 参数省略测试")
    await tester.test(_test_kecode_roundtrip_special_chars, "含分隔符文本往返测试")
    await tester.test(_test_kecode_roundtrip_reference, "reference 往返测试")
    await tester.test(_test_kecode_inline_with_text, "与文本混排切分测试")
    await tester.test(_test_kecode_str_equals_kecode, "字符串化即 KE 码测试")
    await tester.test(_test_kecode_roundtrip_show_on_fallback, "show_on_fallback 往返测试")
    await tester.test(_test_kecode_roundtrip_quote_on_fallback, "quote_on_fallback 往返测试")

    return tester


@func_case
async def test_action_text_fallback(tester: Tester):
    """core.builtins.message.chain: ActionTextElement 降级与保留测试"""
    await tester.test(_test_kept_when_supported, "支持平台保留元素测试")
    await tester.test(_test_degraded_when_unsupported, "不支持平台降级并入测试")
    await tester.test(_test_degraded_creates_element_when_first, "降级为首元素时新建测试")
    await tester.test(_test_degraded_when_markdown_disabled, "enable_markdown 降级测试")
    await tester.test(_test_degraded_when_text_empty, "空 text 降级测试")
    await tester.test(_test_i18n_inner_resolved, "内层多语言翻译测试")
    await tester.test(_test_degraded_suppresses_show, "降级不带出交互提示测试")
    await tester.test(_test_degraded_adds_quotes, "降级补引号测试")

    return tester


@func_case
async def test_action_text_inline(tester: Tester):
    """core.builtins.message.chain: ActionTextElement 行内嵌入测试"""
    await tester.test(_test_inline_in_i18n_kwargs_supported, "句中保留为独立元素测试")
    await tester.test(_test_inline_degraded_merges_into_one_element, "句中降级合并测试")
    await tester.test(_test_inline_trailing_text_follows_element, "元素后文本顺序测试")
    await tester.test(_test_plain_kecode_roundtrip_not_merged, "普通 KE 码往返不合并测试")
    await tester.test(_test_inline_i18n_inner_translated, "句中内层多语言翻译测试")
    await tester.test(_test_i18n_message_chain_structured_roundtrip, "i18n 消息链结构化往返测试")

    return tester


@func_case
async def test_action_text_serialize(tester: Tester):
    """core.builtins.converter: ActionTextElement 跨进程序列化测试"""
    await tester.test(_test_serialize_roundtrip_plain_inner, "纯文本内层往返测试")
    await tester.test(_test_serialize_roundtrip_i18n_inner, "多语言内层往返测试")
    await tester.test(_test_serialize_roundtrip_no_show, "无 show 往返测试")
    await tester.test(_test_serialize_in_message_chain, "消息链整体往返测试")

    return tester
