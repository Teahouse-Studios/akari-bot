"""
Wikitext 离线摘要提取。

本模块只做纯文本处理，不涉及网络请求。
"""

import re

import orjson
import wikitextparser as wtp

from core.logger import Logger

# 这些标签的内容不属于正文：引用来源、图库、代码块等。
# wikitextparser 的 plain_text() 不剥离标签内容，故须在其之前显式清除。
NOISE_TAGS = frozenset(
    {
        "div",
        "gallery",
        "imagemap",
        "maplink",
        "ref",
        "references",
        "score",
        "syntaxhighlight",
        "table",
        "timeline",
    }
)

# 章节标题行，形如 == 标题 == 或 === 子标题 ===
_HEADING = re.compile(r"^={2,6}.*?={2,6}$")

# MediaWiki 行为开关，如 __TOC__、__NOTOC__、__NOEDITSECTION__。
# 它们只控制页面渲染，不属于正文，而 plain_text() 不会剥离
_BEHAVIOR_SWITCH = re.compile(r"__[A-Z][A-Z_]*__")

# 分类链接与跨语言链接的目标前缀，如 Category:、分类:、de:、zh-hans:。
# 这两类链接不出现在渲染后的正文中，但 plain_text() 会把它们还原成链接目标文本
_HIDDEN_LINK = re.compile(
    r"^\s*:?\s*(?:category|分类|分類|カテゴリ|kategorie|categoría|catégorie|категория"
    r"|[a-z]{2,3}(?:-[a-z0-9-]+)?)\s*:",
    re.I,
)

# 语义属性链接 [[属性::值]]，在页面上渲染为其值。值中可含嵌套的内外链接，故须放行一层。
# 须在解析前以文本替换处理：将 WikiLink 的 string 改写成非链接文本会令该对象失效，
# 其后 plain_text() 遍历到它便会抛 AttributeError
_SEMANTIC_LINK = re.compile(r"\[\[[^\[\]|]*?::((?:[^\[\]]|\[\[[^\[\]]*?\]\]|\[[^\[\]]*?\])*?)\]\]")

# 未被 wikitextparser 识别的扩展标签，如 Translate 扩展的 <translate>。
# 这类标签包裹的是正文本身，只去标签、留内容
_RESIDUAL_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9_:-]*(?:\s[^>]*?)?/?>")

# 正文中不应残留的 Wikitext 结构标记。构造一旦不成对或不被识别，这些标记便会原样
# 留在输出里；与其把半段源码充作摘要，不如舍去所在的行，没有正文时宁可不给摘要
_UNPARSED_MARKUP = re.compile(r"\{\{|\}\}|\{\||\|\}|\[\[|\]\]")

# TemplateData 扩展的标签，其内容为描述模板用法的 JSON
_TEMPLATEDATA = re.compile(r"<templatedata\s*>(.*?)</templatedata\s*>", re.I | re.S)

# 句末标点：中英文的句号、问号、叹号。英文标点须后随空白，以免小数点与缩写被误判
_SENTENCE_END = r"(.*?(?:!\s|\?\s|\.\s|！|？|。)).*"
# 首句含开括号时改用此式，取闭括号之后的句末标点，避免在括号内部截断
_SENTENCE_END_AFTER_BRACKET = r"(.*?[)}\]>\"\'》】’”」）].*?(?:!\s|\?\s|\.\s|！|？|。)).*"
_OPEN_BRACKET = r"[({\[>\"\'《【‘“「（]"

# 首句短于此长度时补上第二句。「石头（Stone）是在主世界中大量存在的方块。」为 23 字符，
# 属应当补充的一档；首句本身已逾此长度的条目不再追加
MIN_FIRST_SENTENCE_LENGTH = 40
MAX_SUMMARY_LENGTH = 250
MAX_SUMMARY_LINES = 5


def _strip_braced(text: str) -> str:
    """
    移除成对的 {{...}} 构造，连同其中嵌套的同类构造。

    须在解析前自行扫描，不能一概交给 wikitextparser：构造内部若有裸露的单个花括号
    （如 {{#css:}} 所含的 CSS 规则），其括号配对便会失准，该构造既不算模板也不算
    解析器函数，遂原样留在 plain_text() 的输出里被当作正文。

    只移除成对者。MediaWiki 对孤立的 {{ 按字面文本渲染，其后的正文照常显示，一路
    吞到结尾会连正文一并丢失。

    :param text: 原始 Wikitext。
    :returns: 去除成对 {{...}} 构造后的文本。
    """
    spans = []
    stack = []
    i = 0
    length = len(text)
    while i < length:
        if text.startswith("{{", i):
            stack.append(i)
            i += 2
            continue
        if text.startswith("}}", i):
            if stack:
                start = stack.pop()
                if not stack:  # 最外层构造闭合，整段一并移除
                    spans.append((start, i + 2))
            i += 2
            continue
        i += 1
    if not spans:
        return text
    out = []
    prev = 0
    for start, end in spans:
        out.append(text[prev:start])
        prev = end
    out.append(text[prev:])
    return "".join(out)


def _normalize_section(title: str) -> str:
    """
    归一化章节名以供比较。

    章节锚点中的下划线与标题中的空格等价，wikilib 传入的章节名已将空格换作下划线。

    :param title: 章节名或章节标题。
    :returns: 归一化后的章节名。
    """
    return title.strip().replace("_", " ")


def _select_section(parsed: wtp.WikiText, section: str | None):
    """
    取出目标章节。

    :param parsed: 已解析的 Wikitext。
    :param section: 章节名。为 None 时取引言段。
    :returns: 目标章节对象；未匹配到时返回 None。
    """
    sections = parsed.sections
    if not sections:
        return None
    if not section:
        # wikitextparser 的首个章节即引言段，其 title 为 None
        return sections[0]
    normalized = _normalize_section(section)
    for sec in sections:
        if sec.title is not None and _normalize_section(sec.title) == normalized:
            return sec
    return None


def _templatedata_description(wikitext: str) -> str:
    """
    取出 TemplateData 中的模板说明。

    模板文档页的说明常整个写在 <templatedata> 的 description 字段里，而其外层的
    {{TemplateData|...}} 会被当作模板剥离，正文遂无从取得，摘要只剩「参见」一类的
    章节残留。取回的说明仍是 Wikitext，须由调用方再行清理。

    :param wikitext: 页面的原始 Wikitext。
    :returns: description 字段的原文；无 TemplateData、JSON 不合法或无该字段时返回空字符串。
    """
    match = _TEMPLATEDATA.search(wikitext)
    if not match:
        return ""
    try:
        data = orjson.loads(match.group(1))
    except orjson.JSONDecodeError:
        # 页面上的 TemplateData 未必合法，解析不了便当作没有
        return ""
    if not isinstance(data, dict):
        return ""
    description = data.get("description")
    return description if isinstance(description, str) else ""


def _extract_section_text(wikitext: str, section: str | None) -> str:
    """
    解析 Wikitext 并取出指定章节的正文纯文本。

    :param wikitext: 待解析的 Wikitext。
    :param section: 章节名。为 None 时取引言段。
    :returns: 清理后的纯文本；未匹配到章节时返回空字符串。
    """
    # 行为开关、模板类构造与语义属性链接须在解析前以文本处理：行为开关不构成任何
    # 可识别的节点，模板类构造可能因内含裸花括号而不被识别，改写链接节点则会令其失效
    cleaned = _BEHAVIOR_SWITCH.sub("", wikitext)
    cleaned = _strip_braced(cleaned)
    cleaned = _SEMANTIC_LINK.sub(r"\1", cleaned)
    parsed = wtp.parse(cleaned)
    # 倒序清除，避免靠前的节点被置空后导致靠后节点的 span 偏移
    for tag in reversed(parsed.get_tags()):
        if tag.name in NOISE_TAGS:
            tag.string = ""
    for table in reversed(parsed.get_tables()):
        table.string = ""
    for link in reversed(parsed.wikilinks):
        # 带显示文本的一定是正文中的行内链接，plain_text() 已能正确还原
        if link.text is None and _HIDDEN_LINK.match(link.title):
            link.string = ""

    target = _select_section(parsed, section)
    if target is None:
        return ""
    # 滤去章节标题行与仍带结构标记的残留行，前者一并覆盖目标章节自身的标题
    # 与其下的子章节标题
    lines = [
        line.strip()
        for line in _RESIDUAL_TAG.sub("", target.plain_text()).split("\n")
        if line.strip() and not _HEADING.match(line.strip()) and not _UNPARSED_MARKUP.search(line)
    ]
    return "\n".join(lines)


def extract_summary(wikitext: str, section: str | None = None) -> str:
    """
    离线解析 Wikitext，取出指定章节的正文纯文本。

    模板、文件链接与格式标记由 plain_text() 剥离，表格与引用等噪音节点须在其之前
    显式清除。引言取不到正文时改取 TemplateData 中的模板说明，模板文档页的正文
    往往只写在那里。返回空字符串表示无法离线取得正文。

    :param wikitext: 页面的原始 Wikitext。
    :param section: 章节名。为 None 时取引言段。
    :returns: 清理后的纯文本；解析失败或未匹配到章节时返回空字符串。
    """
    if not wikitext:
        return ""
    try:
        text = _extract_section_text(wikitext, section)
        if not text and not section:
            # TemplateData 只作补充：引言已有散文者以引言为准，指定章节时亦不越俎代庖
            description = _templatedata_description(wikitext)
            if description:
                text = _extract_section_text(description, None)
        return text
    except Exception:
        Logger.exception()
        return ""


def _take_sentence(text: str) -> str | None:
    """
    取出文本开头的一个完整句子。

    :param text: 待取句的文本。
    :returns: 含句末标点的首句；未找到完整句子时返回 None。
    """
    matched = re.findall(_SENTENCE_END, text, re.S | re.M)
    if not matched:
        return None
    if re.findall(_OPEN_BRACKET, matched[0]):
        after_bracket = re.findall(_SENTENCE_END_AFTER_BRACKET, text, re.S | re.M)
        # 括号未闭合时退回首个匹配。此处若直接取下标，空列表会抛 IndexError 并令整段摘要落空
        if after_bracket:
            return after_bracket[0]
    return matched[0]


def truncate_summary(text: str) -> str:
    """
    将正文截断为摘要。

    取开头的一句；首句短于 MIN_FIRST_SENTENCE_LENGTH 时补上第二句。随后应用长度与
    行数上限，超出者末尾附省略号。

    :param text: 待截断的正文纯文本。
    :returns: 截断后的摘要。
    """
    try:
        desc = "\n".join([line for line in text.split("\n") if line != ""])
        first = _take_sentence(desc)
        if first:
            summary = first
            if len(summary) < MIN_FIRST_SENTENCE_LENGTH:
                # 第二句须与首句同处一段。句末标点的匹配跨换行，不加此限制会把
                # TextExtracts 输出中的章节标题、子章节正文一类的无关内容并入摘要
                remainder = desc[len(first) :].split("\n", 1)[0]
                second = _take_sentence(remainder)
                if second:
                    summary += second
            desc = summary
    except Exception:
        Logger.exception()
        desc = ""
    if desc in ["...", "…"]:
        desc = ""
    ellipsis = False
    if len(desc) > MAX_SUMMARY_LENGTH:
        desc = desc[0:MAX_SUMMARY_LENGTH]
        ellipsis = True
    lines = desc.split("\n")
    if len(lines) > MAX_SUMMARY_LINES:
        lines = lines[0:MAX_SUMMARY_LINES]
        ellipsis = True
    return "\n".join(lines) + ("..." if ellipsis else "")
