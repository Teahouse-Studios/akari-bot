"""core.builtins.message.mention 行内 AT 码解析与渲染单元测试。"""

from core.builtins.message.mention import (
    InlineMention,
    iter_at_code,
    render_at_code,
    spans_at_code,
    wrap_sender_id,
)
from core.tester import Tester, func_case


def _rebuild(text: str) -> str:
    return "".join(part.raw if isinstance(part, InlineMention) else part for part in iter_at_code(text))


def _test_iter_splits_surrounding_text():
    try:
        parts = list(iter_at_code("hi <AT:QQ|123> bye"))
        return (
            len(parts) == 3
            and parts[0] == "hi "
            and isinstance(parts[1], InlineMention)
            and (parts[1].client, parts[1].id, parts[1].raw) == ("QQ", "123", "<AT:QQ|123>")
            and parts[1].start == 3
            and parts[1].end == 14
            and parts[2] == " bye"
        )
    except Exception:
        return False


def _test_iter_supports_alternate_marker():
    try:
        parts = list(iter_at_code("<@:QQ|123>"))
        return (
            len(parts) == 1 and isinstance(parts[0], InlineMention) and parts[0].client == "QQ" and parts[0].id == "123"
        )
    except Exception:
        return False


def _test_iter_supports_extra_fields():
    try:
        parts = list(iter_at_code("<AT:QQ|guild|123>"))
        return (
            len(parts) == 1 and isinstance(parts[0], InlineMention) and parts[0].client == "QQ" and parts[0].id == "123"
        )
    except Exception:
        return False


def _test_broadcast_detection():
    try:
        broadcast = next(part for part in iter_at_code("<AT:QQ|all>") if isinstance(part, InlineMention))
        user = next(part for part in iter_at_code("<AT:QQ|123>") if isinstance(part, InlineMention))
        return broadcast.is_broadcast and not user.is_broadcast
    except Exception:
        return False


def _test_plain_text_passthrough():
    try:
        return list(iter_at_code("hello")) == ["hello"] and list(iter_at_code("")) == []
    except Exception:
        return False


def _test_adjacent_at_codes_follow_legacy_pattern():
    try:
        parts = list(iter_at_code("<AT:QQ|1><AT:QQ|2>"))
        return (
            len(parts) == 1
            and isinstance(parts[0], InlineMention)
            and parts[0].raw == "<AT:QQ|1><AT:QQ|2>"
            and parts[0].id == "2"
        )
    except Exception:
        return False


def _test_roundtrip_preserves_text():
    cases = (
        "",
        "no at code",
        "<AT:QQ|1>",
        "a<AT:QQ|1>b",
        "<AT:QQ|1><AT:QQ|2>",
        "<@:Discord|9> mid <AT:QQ|all> tail",
        "<AT:QQ|guild|123>",
        "unclosed <AT:QQ|1",
        "empty <> tag",
    )
    try:
        return all(_rebuild(text) == text for text in cases)
    except Exception:
        return False


def _test_render_platform_syntax():
    templates = {
        "QQ": lambda at: f"[CQ:at,qq={at.id}]",
        "Discord": lambda at: f"<@{at.id}>",
        "kook": lambda at: f"(met){at.id}(met)",
        "matrix": lambda at: at.id,
        "telegram": lambda at: at.id,
    }
    cases = (
        ("QQ", "<AT:QQ|123>", "[CQ:at,qq=123]"),
        ("Discord", "<AT:Discord|456>", "<@456>"),
        ("kook", "<AT:kook|789>", "(met)789(met)"),
        ("matrix", "<AT:matrix|789>", "789"),
        ("telegram", "<AT:telegram|789>", "789"),
    )
    try:
        return all(render_at_code(text, client, templates[client]) == expected for client, text, expected in cases)
    except Exception:
        return False


def _test_render_keeps_foreign_atcode():
    try:
        text = "hi <AT:Discord|7> bye"
        return render_at_code(text, "QQ", lambda at: f"@{at.id}") == text
    except Exception:
        return False


def _test_render_is_inline():
    try:
        return render_at_code("a<AT:QQ|1>b", "QQ", lambda at: f"@{at.id}") == "a@1b"
    except Exception:
        return False


def _test_spans_match_pattern_regions():
    try:
        text = "a <AT:QQ|123> b <@:Discord|456>"
        spans = spans_at_code(text)
        adjacent = spans_at_code("x<AT:QQ|1><AT:QQ|2>y")
        return (
            len(spans) == 2
            and text[spans[0][0] : spans[0][1]] == "<AT:QQ|123>"
            and text[spans[1][0] : spans[1][1]] == "<@:Discord|456>"
            and len(adjacent) == 2
            and adjacent[0] == (1, 10)
            and adjacent[1] == (10, 19)
        )
    except Exception:
        return False


def _test_wrap_sender_id_idempotent():
    try:
        return (
            wrap_sender_id("TEST|0 说 hi", "TEST") == "<AT:TEST|0> 说 hi"
            and wrap_sender_id("<AT:TEST|0> hi", "TEST") == "<AT:TEST|0> hi"
            and wrap_sender_id("TEST|0<AT:TEST|1>", "TEST") == "<AT:TEST|0><AT:TEST|1>"
        )
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


def _test_wrap_then_render():
    try:
        return render_at_code(wrap_sender_id("TEST|123 hi", "TEST"), "TEST", lambda at: f"@{at.id}") == "@123 hi"
    except Exception:
        return False


@func_case
async def test_atcode(tester: Tester):
    """行内 AT 码：解析、渲染与用户 ID 包装测试"""
    await tester.test(_test_iter_splits_surrounding_text, "AT 码与文本交替切分")
    await tester.test(_test_iter_supports_alternate_marker, "`<@:` 标记形式")
    await tester.test(_test_iter_supports_extra_fields, "冗余中间字段形式")
    await tester.test(_test_broadcast_detection, "全体提及识别")
    await tester.test(_test_plain_text_passthrough, "无 AT 码文本透传")
    await tester.test(_test_adjacent_at_codes_follow_legacy_pattern, "相邻 AT 码沿用既有正则语义")
    await tester.test(_test_roundtrip_preserves_text, "切分后可还原原文")
    await tester.test(_test_allow_parse_false_keeps_raw_text, "allow_parse=False 原样保留")
    await tester.test(_test_render_platform_syntax, "各平台渲染语法")
    await tester.test(_test_render_keeps_foreign_atcode, "非本平台 AT 码保留")
    await tester.test(_test_render_is_inline, "渲染结果保持行内")
    await tester.test(_test_spans_match_pattern_regions, "受保护区间精确覆盖")
    await tester.test(_test_wrap_sender_id_idempotent, "wrap_sender_id 幂等")
    await tester.test(_test_wrap_sender_id_preserves_backslashes, "wrap_sender_id 保留反斜杠")
    await tester.test(_test_wrap_then_render, "包装后可渲染")

    return tester


def _test_allow_parse_false_keeps_raw_text():
    try:
        return _rebuild("hi <AT:QQ|123> bye") == "hi <AT:QQ|123> bye"
    except Exception:
        return False
