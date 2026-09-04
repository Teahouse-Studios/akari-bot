import re
from urllib.parse import unquote, urlparse

from attrs import define, field
from bs4 import BeautifulSoup, NavigableString, Tag

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, Markdown, Plain
from core.utils.table import escape_table_cell, resolve_table_columns

DISAMBIGUATION_MAX_BLOCKS = 10
DISAMBIGUATION_MAX_TEXT_LENGTH = 1800
DISAMBIGUATION_TEMPLATES = {
    "Template:Disambiguation",
    "Template:Version disambiguation",
}
_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ol",
    "p",
    "section",
    "table",
    "ul",
}
_SKIP_CLASSES = {
    "catlinks",
    "mw-editsection",
    "navbox",
    "noprint",
    "printfooter",
    "toc",
    "vertical-navbox",
}


@define(frozen=True)
class DisambiguationPart:
    text: str
    target: str | None = None


@define(frozen=True)
class DisambiguationBlock:
    parts: list[DisambiguationPart] = field(factory=list)
    is_title: bool = False

    @property
    def text(self) -> str:
        return "".join(part.text for part in self.parts)


def is_disambiguation_page(pageprops: dict | None, templates: list[str] | None) -> bool:
    """判断 MediaWiki 是否把页面标记为消歧义页。"""
    return "disambiguation" in (pageprops or {}) or bool(DISAMBIGUATION_TEMPLATES.intersection(templates or []))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " "))


def _target_from_anchor(anchor: Tag, base_url: str | None) -> str | None:
    classes = set(anchor.get("class", []))
    if classes.intersection({"external", "extiw"}):
        return None
    href = anchor.get("href", "")
    if not href or href.startswith(("#", "mailto:")):
        return None
    target = anchor.get("title")
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc:
        base = urlparse(base_url or "")
        if not base.netloc or parsed.netloc.casefold() != base.netloc.casefold():
            return None
    if not target and parsed.query:
        for item in parsed.query.split("&"):
            key, _, value = item.partition("=")
            if key == "title" and value:
                target = unquote(value).replace("_", " ")
                break
    if not target:
        match = re.search(r"/(?:wiki|w)/(.*)$", parsed.path)
        if match:
            target = unquote(match.group(1)).replace("_", " ")
    if target and parsed.fragment and "#" not in target:
        target += "#" + unquote(parsed.fragment).replace("_", " ")
    return target


def _append_part(parts: list[DisambiguationPart], text: str, target: str | None = None) -> None:
    text = "\n" if text == "\n" else _normalize_text(text)
    if not text:
        return
    if parts and parts[-1].target == target:
        previous = parts[-1]
        parts[-1] = DisambiguationPart(previous.text + text, target)
    else:
        parts.append(DisambiguationPart(text, target))


def _collect_inline(node: Tag, parts: list[DisambiguationPart], base_url: str | None) -> None:
    for child in node.children:
        if isinstance(child, NavigableString):
            _append_part(parts, str(child))
            continue
        if not isinstance(child, Tag):
            continue
        classes = set(child.get("class", []))
        if child.name in {"script", "style"} or classes.intersection(_SKIP_CLASSES):
            continue
        if child.name == "br":
            _append_part(parts, "\n")
        elif child.name == "a":
            label = _normalize_text(child.get_text("", strip=False))
            if label.strip():
                _append_part(parts, label, _target_from_anchor(child, base_url))
        elif child.name not in {"dl", "ol", "table", "ul"}:
            _collect_inline(child, parts, base_url)


def _block_from_tag(tag: Tag, base_url: str | None) -> DisambiguationBlock | None:
    parts: list[DisambiguationPart] = []
    _collect_inline(tag, parts, base_url)
    if not parts:
        return None
    first = parts[0]
    last = parts[-1]
    parts[0] = DisambiguationPart(first.text.lstrip(), first.target)
    parts[-1] = DisambiguationPart(last.text.rstrip(), last.target)
    parts = [part for part in parts if part.text]
    return (
        DisambiguationBlock(parts, is_title=tag.name in {"dt", "h1", "h2", "h3", "h4", "h5", "h6"}) if parts else None
    )


def _extract_blocks(tag: Tag, base_url: str | None) -> list[DisambiguationBlock]:
    classes = set(tag.get("class", []))
    if tag.name in {"script", "style"} or classes.intersection(_SKIP_CLASSES):
        return []
    if "disambig" in classes and "footnote" in classes:
        return []
    if tag.name in {"ol", "ul"}:
        blocks = []
        for item in tag.find_all("li", recursive=False):
            if block := _block_from_tag(item, base_url):
                blocks.append(block)
            for nested in item.find_all(["ol", "ul"], recursive=False):
                blocks.extend(_extract_blocks(nested, base_url))
        return blocks
    if tag.name == "dl":
        return [
            block
            for child in tag.find_all(["dt", "dd"], recursive=False)
            if (block := _block_from_tag(child, base_url))
        ]
    if tag.name == "table":
        return [block for row in tag.find_all("tr") if (block := _block_from_tag(row, base_url))]
    direct_blocks = [
        child
        for child in tag.children
        if isinstance(child, Tag)
        and child.name in _BLOCK_TAGS
        and not set(child.get("class", [])).intersection(_SKIP_CLASSES)
    ]
    if tag.name in {"article", "div", "section"} and direct_blocks and "msgbox" not in classes:
        blocks = []
        for child in direct_blocks:
            blocks.extend(_extract_blocks(child, base_url))
        return blocks
    block = _block_from_tag(tag, base_url)
    return [block] if block else []


def parse_disambiguation_html(html: str, base_url: str | None = None) -> list[DisambiguationBlock]:
    """解析 MediaWiki 渲染正文，并保留同站内部链接的页面目标。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".mw-parser-output") or soup
    blocks = []
    for child in root.children:
        if isinstance(child, Tag):
            blocks.extend(_extract_blocks(child, base_url))
    return blocks


def is_disambiguation_overlong(blocks: list[DisambiguationBlock]) -> bool:
    return (
        len(blocks) > DISAMBIGUATION_MAX_BLOCKS
        or sum(len(block.text) for block in blocks) > DISAMBIGUATION_MAX_TEXT_LENGTH
    )


def _block_elements(
    block: DisambiguationBlock,
    command_prefix: str,
    interwiki_prefix: str,
) -> list:
    elements = []
    for part in block.parts:
        if part.target:
            elements.append(ActionText(f"{command_prefix}wiki {interwiki_prefix}{part.target}", show=part.text))
        else:
            elements.append(Plain(part.text, disable_joke=True))
    return elements


def build_disambiguation_text(
    blocks: list[DisambiguationBlock],
    command_prefix: str,
    interwiki_prefix: str = "",
) -> MessageChain:
    chain = MessageChain.create()
    for index, block in enumerate(blocks):
        if index:
            chain.append(Plain("\n", disable_joke=True))
        chain.extend(_block_elements(block, command_prefix, interwiki_prefix))
    chain.append(Plain("\n", disable_joke=True))
    return chain


def build_disambiguation_table(
    blocks: list[DisambiguationBlock],
    command_prefix: str,
    header: str,
    interwiki_prefix: str = "",
) -> MessageChain:
    blocks = [block for block in blocks if not block.is_title]
    columns = resolve_table_columns([len(blocks)], minimum=2)
    escaped_header = escape_table_cell(header)
    pending = "|" + f" {escaped_header} |" * columns + f"\n|{'---|' * columns}\n| "
    chain = MessageChain.create()
    for index, block in enumerate(blocks):
        for part in block.parts:
            display = escape_table_cell(part.text)
            if part.target:
                if pending:
                    chain.append(Markdown(pending, disable_joke=True))
                    pending = ""
                chain.append(ActionText(f"{command_prefix}wiki {interwiki_prefix}{part.target}", show=display))
            else:
                pending += display
        if index + 1 == len(blocks):
            padding = (columns - (index + 1) % columns) % columns
            pending += " |" * (padding + 1) + "\n"
        elif (index + 1) % columns == 0:
            pending += " |\n| "
        else:
            pending += " | "
    chain.append(Markdown(pending, disable_joke=True))
    return chain
