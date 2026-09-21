"""wiki 摘要离线提取单元测试 - Wikitext 解析与噪音剥离。"""

from pathlib import Path

from core.tester import func_case, Tester
from modules.wiki.utils.summarize import extract_summary, truncate_summary

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "wikitext" / "mcwiki_stone.wikitext"


async def _test_lead_skips_infobox_and_hatnote():
    try:
        src = (
            "{{about|方块|其他用法|石头 (消歧义)}}\n"
            "{{Infobox block\n|image=Stone.png\n|light=0\n}}\n\n"
            "'''石头'''是一种在[[主世界]]中大量[[生成]]的[[方块]]。"
        )
        return extract_summary(src) == "石头是一种在主世界中大量生成的方块。"

    except Exception:
        return False


async def _test_ref_content_not_inlined():
    try:
        src = "'''乙'''是<ref name=x>来源文本</ref>一种装置<!--注释-->。"
        return extract_summary(src) == "乙是一种装置。"

    except Exception:
        return False


async def _test_table_before_lead_removed():
    try:
        src = "{| class=wikitable\n! 头\n|-\n| 值\n|}\n'''丙'''是一种东西。"
        return extract_summary(src) == "丙是一种东西。"

    except Exception:
        return False


async def _test_div_notice_removed():
    try:
        src = "<div class='notice'>顶部提示</div>\n'''丁'''是第四个。"
        return extract_summary(src) == "丁是第四个。"

    except Exception:
        return False


async def _test_inline_template_leaves_sentence_readable():
    try:
        src = "'''甲'''是一种{{lang|en|Widget}}装置，用于测试。"
        return extract_summary(src) == "甲是一种装置，用于测试。"

    except Exception:
        return False


async def _test_section_selected():
    try:
        src = "引言内容。\n\n== 获取 ==\n获取方式说明。\n\n=== 挖掘 ===\n子节内容。"
        return extract_summary(src, "获取") == "获取方式说明。\n子节内容。"

    except Exception:
        return False


async def _test_section_underscore_matches_space():
    try:
        src = "引言。\n\n== 合成 表 ==\n合成表内容。"
        return extract_summary(src, "合成_表") == "合成表内容。"

    except Exception:
        return False


async def _test_section_missing_returns_empty():
    try:
        src = "引言。\n\n== 获取 ==\n内容。"
        return extract_summary(src, "不存在的章节") == ""

    except Exception:
        return False


async def _test_lead_all_templates_returns_empty():
    try:
        src = "{{Stub}}\n{{Infobox|a=b}}\n\n== 历史 ==\n内容在这里。"
        return extract_summary(src) == ""

    except Exception:
        return False


async def _test_behavior_switch_removed():
    try:
        src = "{{面包屑|角色}}{{角色导航}}\n\n__TOC__\n{{角色\n|名称=甘雨\n}}"
        return extract_summary(src) == ""

    except Exception:
        return False


async def _test_behavior_switch_kept_text():
    try:
        src = "__NOTOC__\n'''甲'''是一种装置。"
        return extract_summary(src) == "甲是一种装置。"

    except Exception:
        return False


async def _test_category_and_langlink_removed():
    try:
        src = "[[Category:Arch projects]]\n[[de:Pacman]]\n[[es:Pacman]]\n'''pacman''' is a package manager."
        return extract_summary(src) == "pacman is a package manager."

    except Exception:
        return False


async def _test_inline_links_kept():
    try:
        src = "甲是一种[[主世界]]的[[方块]]，详见[[w:Foo|这篇文章]]。"
        return extract_summary(src) == "甲是一种主世界的方块，详见这篇文章。"

    except Exception:
        return False


async def _test_residual_tag_unwrapped():
    try:
        src = "<translate>\nPortage is the manager.\n</translate>"
        return extract_summary(src) == "Portage is the manager."

    except Exception:
        return False


async def _test_semantic_property_link():
    try:
        src = "Portage is [[Article description::the official package manager]]. It works."
        return extract_summary(src) == "Portage is the official package manager. It works."

    except Exception:
        return False


async def _test_semantic_property_link_nested():
    try:
        src = (
            "'''Portage''' is [[Article description::the official "
            "[[Wikipedia:Package manager|package manager]] and "
            "[https://www.gentoo.org/ distribution system] for Gentoo.]] It functions as the heart."
        )
        return extract_summary(src) == (
            "Portage is the official package manager and distribution system for Gentoo. It functions as the heart."
        )

    except Exception:
        return False


async def _test_braced_construct_with_bare_braces_removed():
    try:
        src = "{{面包屑}}\n{{#css:\n.freeze th,.freeze td{\nposition:sticky;\ntop:55px;\n}\n}}"
        return extract_summary(src) == ""

    except Exception:
        return False


async def _test_braced_construct_keeps_neighbouring_text():
    try:
        src = "'''甲'''是一种装置。{{#css:\n.a{\nb:c;\n}\n}}"
        return extract_summary(src) == "甲是一种装置。"

    except Exception:
        return False


async def _test_unclosed_brace_does_not_swallow_text():
    try:
        src = "{{未闭合的构造\n'''甲'''是一种装置。"
        return extract_summary(src) == "甲是一种装置。"

    except Exception:
        return False


async def _test_unparsed_markup_lines_dropped():
    try:
        return all(
            extract_summary(src) == "正文一句话。"
            for src in (
                "{|class=wikitable 残缺表格\n正文一句话。",
                "[[未闭合链接\n正文一句话。",
                "}}\n正文一句话。",
            )
        )

    except Exception:
        return False


async def _test_all_residue_yields_no_summary():
    try:
        return extract_summary("{{未闭合的构造\n[[也未闭合") == ""

    except Exception:
        return False


async def _test_templatedata_description_used_as_fallback():
    try:
        src = (
            "{{documentation header}}\n"
            "{{shortcut|editing}}\n\n"
            "{{TemplateData|<templatedata>\n"
            '{\n\t"params": {},\n'
            '\t"description": "此模板用于标记正在进行重大编辑的页面。目的是为了防止[[Help:编辑冲突|编辑冲突]]。"\n'
            "}\n</templatedata>}}\n\n"
            "== 参见 ==\n{{Maintenance see also}}"
        )
        return extract_summary(src) == "此模板用于标记正在进行重大编辑的页面。目的是为了防止编辑冲突。"

    except Exception:
        return False


async def _test_templatedata_not_used_when_lead_present():
    try:
        src = (
            "'''甲模板'''用于测试。\n\n"
            "{{TemplateData|<templatedata>\n"
            '{"description": "这是 TemplateData 里的说明。"}\n'
            "</templatedata>}}"
        )
        return extract_summary(src) == "甲模板用于测试。"

    except Exception:
        return False


async def _test_malformed_templatedata_yields_no_summary():
    try:
        src = "{{TemplateData|<templatedata>\n{ 这不是合法的 JSON\n</templatedata>}}"
        return extract_summary(src) == ""

    except Exception:
        return False


async def _test_empty_input_returns_empty():
    try:
        return extract_summary("") == "" and extract_summary("", "章节") == ""

    except Exception:
        return False


async def _test_real_page_lead():
    try:
        src = _FIXTURE.read_text(encoding="utf-8")
        return extract_summary(src) == "石头（Stone）是在主世界中大量存在的方块。"

    except Exception:
        return False


async def _test_short_first_sentence_gets_second():
    try:
        src = "石头（Stone）是在主世界中大量存在的方块。它可以用镐开采。第三句在此。"
        return truncate_summary(src) == "石头（Stone）是在主世界中大量存在的方块。它可以用镐开采。"

    except Exception:
        return False


async def _test_long_first_sentence_stays_alone():
    try:
        src = "石头是一种在主世界中大量生成的方块，也是玩家在游戏早期最常接触到的建筑材料之一。它可以用镐开采。"
        return (
            truncate_summary(src) == "石头是一种在主世界中大量生成的方块，也是玩家在游戏早期最常接触到的建筑材料之一。"
        )

    except Exception:
        return False


async def _test_single_sentence_stays_single():
    try:
        src = "石头（Stone）是在主世界中大量存在的方块。"
        return truncate_summary(src) == "石头（Stone）是在主世界中大量存在的方块。"

    except Exception:
        return False


async def _test_bracket_not_split():
    try:
        src = "石头（Stone）是一种方块。"
        return truncate_summary(src) == "石头（Stone）是一种方块。"

    except Exception:
        return False


async def _test_unclosed_bracket_not_dropped():
    try:
        src = "石头（Stone是一种方块。它很常见。"
        return truncate_summary(src) == "石头（Stone是一种方块。它很常见。"

    except Exception:
        return False


async def _test_english_sentences():
    try:
        src = "Foo is a bar. It was made in 1999. Third one."
        return truncate_summary(src) == "Foo is a bar. It was made in 1999. "

    except Exception:
        return False


async def _test_no_terminator_kept_as_is():
    try:
        return truncate_summary("这是一个没有句号的文本") == "这是一个没有句号的文本"

    except Exception:
        return False


async def _test_length_cap_appends_ellipsis():
    try:
        src = "甲" * 300
        result = truncate_summary(src)
        return result == "甲" * 250 + "..."

    except Exception:
        return False


async def _test_second_sentence_not_across_paragraph():
    try:
        src = "石头（Stone）是在主世界中大量存在的方块。\n生成\n自然生成\n在主世界中，石头会在Y=0以上的高度生成。"
        return truncate_summary(src) == "石头（Stone）是在主世界中大量存在的方块。"

    except Exception:
        return False


async def _test_ellipsis_only_becomes_empty():
    try:
        return truncate_summary("…") == "" and truncate_summary("...") == ""

    except Exception:
        return False


async def _test_truncate_empty_stays_empty():
    try:
        return truncate_summary("") == "" and truncate_summary("\n\n") == ""

    except Exception:
        return False


@func_case
async def test_wiki_summary(tester: Tester):
    """wiki 摘要离线提取：Wikitext 解析与噪音剥离测试"""
    await tester.test(_test_lead_skips_infobox_and_hatnote, "信息框与顶部提示剥离测试")
    await tester.test(_test_ref_content_not_inlined, "引用内容不混入测试")
    await tester.test(_test_table_before_lead_removed, "引言前表格剥离测试")
    await tester.test(_test_div_notice_removed, "提示框剥离测试")
    await tester.test(_test_inline_template_leaves_sentence_readable, "内联模板剥离测试")
    await tester.test(_test_section_selected, "章节定位测试")
    await tester.test(_test_section_underscore_matches_space, "章节下划线等价测试")
    await tester.test(_test_section_missing_returns_empty, "章节未命中返回空测试")
    await tester.test(_test_lead_all_templates_returns_empty, "引言全模板返回空测试")
    await tester.test(_test_behavior_switch_removed, "行为开关魔术字剥离测试")
    await tester.test(_test_behavior_switch_kept_text, "行为开关剥离不伤正文测试")
    await tester.test(_test_category_and_langlink_removed, "分类与跨语言链接剥离测试")
    await tester.test(_test_inline_links_kept, "普通链接不误伤测试")
    await tester.test(_test_residual_tag_unwrapped, "残留标签去除保留正文测试")
    await tester.test(_test_semantic_property_link, "语义属性链接还原测试")
    await tester.test(_test_semantic_property_link_nested, "语义属性链接嵌套还原测试")
    await tester.test(_test_braced_construct_with_bare_braces_removed, "裸花括号构造剥离测试")
    await tester.test(_test_braced_construct_keeps_neighbouring_text, "裸花括号构造不伤正文测试")
    await tester.test(_test_unclosed_brace_does_not_swallow_text, "未闭合花括号不吞正文测试")
    await tester.test(_test_unparsed_markup_lines_dropped, "残留标记行滤除测试")
    await tester.test(_test_all_residue_yields_no_summary, "全为残留时无摘要测试")
    await tester.test(_test_templatedata_description_used_as_fallback, "TemplateData 说明取用测试")
    await tester.test(_test_templatedata_not_used_when_lead_present, "有引言时不取 TemplateData 测试")
    await tester.test(_test_malformed_templatedata_yields_no_summary, "TemplateData 非法 JSON 测试")
    await tester.test(_test_empty_input_returns_empty, "空输入测试")
    await tester.test(_test_real_page_lead, "真实样本首句测试")
    await tester.test(_test_short_first_sentence_gets_second, "短首句补第二句测试")
    await tester.test(_test_long_first_sentence_stays_alone, "长首句不追加测试")
    await tester.test(_test_single_sentence_stays_single, "单句停在一句测试")
    await tester.test(_test_bracket_not_split, "括号内不截断测试")
    await tester.test(_test_unclosed_bracket_not_dropped, "括号未闭合不丢摘要测试")
    await tester.test(_test_english_sentences, "英文句末标点测试")
    await tester.test(_test_no_terminator_kept_as_is, "无句末标点保留原文测试")
    await tester.test(_test_length_cap_appends_ellipsis, "长度上限省略号测试")
    await tester.test(_test_second_sentence_not_across_paragraph, "第二句不跨段落测试")
    await tester.test(_test_ellipsis_only_becomes_empty, "纯省略号视作无摘要测试")
    await tester.test(_test_truncate_empty_stays_empty, "空正文保持无摘要测试")

    return tester
