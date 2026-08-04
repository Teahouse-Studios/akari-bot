"""wiki 摘要离线提取单元测试 - Wikitext 解析与噪音剥离。

未启用 TextExtracts 扩展的 Wiki 此前取整页渲染 HTML 转纯文本，信息框与顶部提示会被
展平排在正文之前，摘要因而常截到消歧义提示而非正文首句。改为离线解析 Wikitext 后，
这些用例即为守住「取到的是正文」这条不变量。
"""

from pathlib import Path

from core.tester import func_case, Tester
from modules.wiki.utils.summarize import extract_summary, truncate_summary

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "wikitext" / "mcwiki_stone.wikitext"


async def _test_lead_skips_infobox_and_hatnote():
    """测试引言提取 - 信息框与顶部提示模板不进入摘要"""
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
    """测试噪音剥离 - 引用来源的内容不得混入正文

    plain_text() 不剥离标签内容，未经清除时此例会得到「乙是来源文本一种装置。」。
    """
    try:
        src = "'''乙'''是<ref name=x>来源文本</ref>一种装置<!--注释-->。"
        return extract_summary(src) == "乙是一种装置。"

    except Exception:
        return False


async def _test_table_before_lead_removed():
    """测试噪音剥离 - 引言前的表格不进入摘要"""
    try:
        src = "{| class=wikitable\n! 头\n|-\n| 值\n|}\n'''丙'''是一种东西。"
        return extract_summary(src) == "丙是一种东西。"

    except Exception:
        return False


async def _test_div_notice_removed():
    """测试噪音剥离 - 顶部提示框不进入摘要"""
    try:
        src = "<div class='notice'>顶部提示</div>\n'''丁'''是第四个。"
        return extract_summary(src) == "丁是第四个。"

    except Exception:
        return False


async def _test_inline_template_leaves_sentence_readable():
    """测试模板剥离 - 内联模板被剥离后句子仍然通顺

    内联模板未经展开，其文本无从取得，剥离后句子结构应保持完整。
    """
    try:
        src = "'''甲'''是一种{{lang|en|Widget}}装置，用于测试。"
        return extract_summary(src) == "甲是一种装置，用于测试。"

    except Exception:
        return False


async def _test_section_selected():
    """测试章节定位 - 取到指定章节且不含章节标题行"""
    try:
        src = "引言内容。\n\n== 获取 ==\n获取方式说明。\n\n=== 挖掘 ===\n子节内容。"
        return extract_summary(src, "获取") == "获取方式说明。\n子节内容。"

    except Exception:
        return False


async def _test_section_underscore_matches_space():
    """测试章节定位 - 锚点中的下划线与章节标题中的空格等价

    wikilib 传入的章节名已将空格换作下划线，比较前须还原。
    """
    try:
        src = "引言。\n\n== 合成 表 ==\n合成表内容。"
        return extract_summary(src, "合成_表") == "合成表内容。"

    except Exception:
        return False


async def _test_section_missing_returns_empty():
    """测试章节定位 - 未匹配到章节时返回空字符串以触发回退"""
    try:
        src = "引言。\n\n== 获取 ==\n内容。"
        return extract_summary(src, "不存在的章节") == ""

    except Exception:
        return False


async def _test_lead_all_templates_returns_empty():
    """测试回退信号 - 引言全由模板构成时返回空字符串

    此类页面的正文无从离线取得，须交由调用方回退至渲染 HTML。
    """
    try:
        src = "{{Stub}}\n{{Infobox|a=b}}\n\n== 历史 ==\n内容在这里。"
        return extract_summary(src) == ""

    except Exception:
        return False


async def _test_behavior_switch_removed():
    """测试噪音剥离 - 行为开关魔术字不进入摘要

    引言仅有模板与 __TOC__ 的页面须返回空以触发回退，否则摘要会变成「__TOC__」。
    """
    try:
        src = "{{面包屑|角色}}{{角色导航}}\n\n__TOC__\n{{角色\n|名称=甘雨\n}}"
        return extract_summary(src) == ""

    except Exception:
        return False


async def _test_behavior_switch_kept_text():
    """测试噪音剥离 - 剥离行为开关不影响同页正文"""
    try:
        src = "__NOTOC__\n'''甲'''是一种装置。"
        return extract_summary(src) == "甲是一种装置。"

    except Exception:
        return False


async def _test_category_and_langlink_removed():
    """测试噪音剥离 - 分类与跨语言链接不进入摘要

    这两类链接在渲染时并不出现于正文，但 plain_text() 会把它们还原成
    「Category:X」「de:X」一类的文本排在首句之前。
    """
    try:
        src = "[[Category:Arch projects]]\n[[de:Pacman]]\n[[es:Pacman]]\n'''pacman''' is a package manager."
        return extract_summary(src) == "pacman is a package manager."

    except Exception:
        return False


async def _test_inline_links_kept():
    """测试噪音剥离 - 剥离隐藏链接不得误伤正文中的普通链接与带显示文本的链接"""
    try:
        src = "甲是一种[[主世界]]的[[方块]]，详见[[w:Foo|这篇文章]]。"
        return extract_summary(src) == "甲是一种主世界的方块，详见这篇文章。"

    except Exception:
        return False


async def _test_residual_tag_unwrapped():
    """测试噪音剥离 - 未识别的扩展标签去除但保留其中正文

    Translate 扩展的 <translate> 包裹的是正文本身，不可连内容一并删除。
    """
    try:
        src = "<translate>\nPortage is the manager.\n</translate>"
        return extract_summary(src) == "Portage is the manager."

    except Exception:
        return False


async def _test_semantic_property_link():
    """测试链接还原 - 语义属性链接取双冒号之后的显示值"""
    try:
        src = "Portage is [[Article description::the official package manager]]. It works."
        return extract_summary(src) == "Portage is the official package manager. It works."

    except Exception:
        return False


async def _test_semantic_property_link_nested():
    """测试链接还原 - 语义属性链接的值中含嵌套链接时同样还原

    Gentoo Wiki 的条目首句即属此形，值里嵌着内链与外链。
    """
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
    """测试噪音剥离 - 内部含裸花括号的构造不进入摘要

    {{#css:}} 一类解析器函数内部的 CSS 规则带有单个花括号，wikitextparser 便无法
    将其识别为模板或解析器函数，会原样留在 plain_text() 的输出里被当作正文。
    wiki.biligame.com 的「角色筛选」页即因此把整段 CSS 当成了摘要。
    """
    try:
        src = "{{面包屑}}\n{{#css:\n.freeze th,.freeze td{\nposition:sticky;\ntop:55px;\n}\n}}"
        return extract_summary(src) == ""

    except Exception:
        return False


async def _test_braced_construct_keeps_neighbouring_text():
    """测试噪音剥离 - 移除含裸花括号的构造不伤及同处一行的正文"""
    try:
        src = "'''甲'''是一种装置。{{#css:\n.a{\nb:c;\n}\n}}"
        return extract_summary(src) == "甲是一种装置。"

    except Exception:
        return False


async def _test_unclosed_brace_does_not_swallow_text():
    """测试噪音剥离 - 未闭合的双花括号不得吞掉其后的正文

    MediaWiki 对孤立的 {{ 按字面文本渲染，其后的正文照常显示，故扫描只可移除
    成对的构造。残留的标记行由兜底防线滤去，正文须留下。
    """
    try:
        src = "{{未闭合的构造\n'''甲'''是一种装置。"
        return extract_summary(src) == "甲是一种装置。"

    except Exception:
        return False


async def _test_unparsed_markup_lines_dropped():
    """测试兜底防线 - 仍带 Wikitext 结构标记的行不充作摘要

    解析未能识别的构造会把源码标记原样留在输出里。与其把半段源码当作摘要，不如
    舍去该行。此处逐一覆盖残缺表格、未闭合链接与游离的右花括号。
    """
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
    """测试兜底防线 - 整段皆为解析残留时不给摘要

    对应 wiki.biligame.com「角色筛选」一类页面：通篇模板与表格，没有正文可言，
    此时宁可不给摘要，只给出链接。
    """
    try:
        return extract_summary("{{未闭合的构造\n[[也未闭合") == ""

    except Exception:
        return False


async def _test_templatedata_description_used_as_fallback():
    """测试模板文档 - 正文写在 TemplateData 里时须能取到

    模板文档页的说明常整个写在 <templatedata> 的 description 字段中，而其外层的
    {{TemplateData|...}} 会被当作模板剥离，正文遂无从取得，摘要只剩「参见」一类的
    章节残留。zh.minecraft.wiki 的 Template:Currently editing/doc 即属此形。
    """
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
    """测试模板文档 - 引言本身有正文时不取 TemplateData

    TemplateData 只作补充，引言已有散文者以引言为准。
    """
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
    """测试模板文档 - TemplateData 不是合法 JSON 时不给摘要，也不得抛出异常"""
    try:
        src = "{{TemplateData|<templatedata>\n{ 这不是合法的 JSON\n</templatedata>}}"
        return extract_summary(src) == ""

    except Exception:
        return False


async def _test_empty_input_returns_empty():
    """测试边界 - 空输入返回空字符串"""
    try:
        return extract_summary("") == "" and extract_summary("", "章节") == ""

    except Exception:
        return False


async def _test_real_page_lead():
    """测试真实样本 - 模板堆叠的条目取到正文首句

    样本引言段开头连着 about、Infobox、relevant tutorial、Quote 四个模板，
    改造前的 HTML 管线在此会截到 about 渲染出的消歧义提示。
    """
    try:
        src = _FIXTURE.read_text(encoding="utf-8")
        return extract_summary(src) == "石头（Stone）是在主世界中大量存在的方块。"

    except Exception:
        return False


async def _test_short_first_sentence_gets_second():
    """测试自适应句数 - 首句短于阈值时补上第二句"""
    try:
        src = "石头（Stone）是在主世界中大量存在的方块。它可以用镐开采。第三句在此。"
        return truncate_summary(src) == "石头（Stone）是在主世界中大量存在的方块。它可以用镐开采。"

    except Exception:
        return False


async def _test_long_first_sentence_stays_alone():
    """测试自适应句数 - 首句达到阈值时不再追加"""
    try:
        src = "石头是一种在主世界中大量生成的方块，也是玩家在游戏早期最常接触到的建筑材料之一。它可以用镐开采。"
        return (
            truncate_summary(src) == "石头是一种在主世界中大量生成的方块，也是玩家在游戏早期最常接触到的建筑材料之一。"
        )

    except Exception:
        return False


async def _test_single_sentence_stays_single():
    """测试自适应句数 - 正文只有一句时停在一句"""
    try:
        src = "石头（Stone）是在主世界中大量存在的方块。"
        return truncate_summary(src) == "石头（Stone）是在主世界中大量存在的方块。"

    except Exception:
        return False


async def _test_bracket_not_split():
    """测试括号保护 - 不在括号内部截断

    首句含开括号时改取闭括号之后的句末标点，否则「石头（Stone）是……」会在全角
    左括号处断掉。
    """
    try:
        src = "石头（Stone）是一种方块。"
        return truncate_summary(src) == "石头（Stone）是一种方块。"

    except Exception:
        return False


async def _test_unclosed_bracket_not_dropped():
    """测试括号保护 - 括号未闭合时不得丢失整段摘要

    原实现在此会因取空列表下标抛 IndexError 并被吞掉，摘要变成空字符串。
    """
    try:
        src = "石头（Stone是一种方块。它很常见。"
        return truncate_summary(src) == "石头（Stone是一种方块。它很常见。"

    except Exception:
        return False


async def _test_english_sentences():
    """测试自适应句数 - 英文句末标点同样生效"""
    try:
        src = "Foo is a bar. It was made in 1999. Third one."
        return truncate_summary(src) == "Foo is a bar. It was made in 1999. "

    except Exception:
        return False


async def _test_no_terminator_kept_as_is():
    """测试边界 - 无句末标点时保留原文交由长度上限处理"""
    try:
        return truncate_summary("这是一个没有句号的文本") == "这是一个没有句号的文本"

    except Exception:
        return False


async def _test_length_cap_appends_ellipsis():
    """测试长度上限 - 超出上限时截断并附省略号"""
    try:
        src = "甲" * 300
        result = truncate_summary(src)
        return result == "甲" * 250 + "..."

    except Exception:
        return False


async def _test_second_sentence_not_across_paragraph():
    """测试自适应句数 - 第二句不跨段落续接

    TextExtracts 的输出含章节标题，离线解析的输出含子章节正文，跨段续接会把
    「生成」「自然生成」一类的标题并入摘要。
    """
    try:
        src = "石头（Stone）是在主世界中大量存在的方块。\n生成\n自然生成\n在主世界中，石头会在Y=0以上的高度生成。"
        return truncate_summary(src) == "石头（Stone）是在主世界中大量存在的方块。"

    except Exception:
        return False


async def _test_ellipsis_only_becomes_empty():
    """测试边界 - 内容仅为省略号时视作无摘要"""
    try:
        return truncate_summary("…") == "" and truncate_summary("...") == ""

    except Exception:
        return False


async def _test_truncate_empty_stays_empty():
    """测试边界 - 空正文截断后仍为空

    离线解析取不到正文时返回空字符串，摘要须一路保持为空，调用方据此只给出链接。
    解析失败已不再回退至渲染 HTML，故这条链路是「无摘要」的唯一出口。
    """
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
