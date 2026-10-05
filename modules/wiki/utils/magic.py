import asyncio
from urllib.parse import parse_qs, urljoin, urlsplit

import wikitextparser as wtp
from attrs import define
from bs4 import BeautifulSoup

from core.builtins.message.internal import I18NContext
from core.utils.container import ExpiringTempDict
from .wikilib import InvalidWikiError, WikiLib

MAX_EXPRESSION_LENGTH = 400
MAX_EXPRESSION_DEPTH = 5
MAX_EXPRESSION_NODES = 12
MAX_RESULT_LENGTH = 200
MAX_INLINE_MAGIC_RESULTS = 3
MAGIC_TIMEOUT = 8

_SITE_VARIABLES = {
    "sitename",
    "server",
    "servername",
    "currentversion",
    "contentlanguage",
    "scriptpath",
    "articlepath",
    "numberofarticles",
    "numberoffiles",
    "numberofedits",
    "numberofusers",
    "numberofactiveusers",
    "numberofpages",
    "numberofadmins",
}
_TIME_VARIABLES = {
    prefix + suffix
    for prefix in ("current", "local")
    for suffix in (
        "year",
        "month",
        "month1",
        "monthname",
        "monthabbrev",
        "day",
        "day2",
        "dayname",
        "dow",
        "week",
        "time",
        "hour",
        "timestamp",
    )
}
_TITLE_VARIABLES = {
    "pagename",
    "pagenamee",
    "fullpagename",
    "fullpagenamee",
    "basepagename",
    "basepagenamee",
    "rootpagename",
    "rootpagenamee",
    "subpagename",
    "subpagenamee",
    "namespace",
    "namespacee",
    "namespacenumber",
    "talkspace",
    "talkspacee",
    "subjectspace",
    "subjectspacee",
    "talkpagename",
    "talkpagenamee",
    "subjectpagename",
    "subjectpagenamee",
}
_HASH_FUNCTIONS = {"expr", "if", "ifeq", "ifexpr", "iferror", "switch", "time", "timel", "urldecode"}
_COLON_FUNCTIONS = {
    "urlencode",
    "anchorencode",
    "fullurl",
    "canonicalurl",
    "localurl",
    "lc",
    "uc",
    "lcfirst",
    "ucfirst",
    "formatnum",
    "ns",
    "nse",
}
_URL_FUNCTIONS = {"fullurl", "canonicalurl", "localurl"}
_SUPPORTED_WORDS = _SITE_VARIABLES | _TIME_VARIABLES | _TITLE_VARIABLES | _HASH_FUNCTIONS | _COLON_FUNCTIONS
_REGISTRY_CACHE = ExpiringTempDict(exp=43200)


class MagicWordError(Exception):
    def __init__(self, key: str):
        self.key = "wiki.message.magic." + key
        super().__init__(self.key)


@define(frozen=True)
class MagicCall:
    name: str
    label: str
    needs_page: bool = False


def _head(node) -> tuple[str, bool, bool]:
    body = str(node)[2:-2].split("|", 1)[0]
    head, separator, _argument = body.partition(":")
    head = head.strip()
    return head.removeprefix("#"), head.startswith("#"), bool(separator)


def extract_expressions(text: str) -> list:
    parsed = wtp.parse(text)
    nodes = {node.span: node for node in [*parsed.templates, *parsed.parser_functions]}
    ignored = [item.span for item in parsed.parameters]
    ignored.extend(
        tag.span
        for tag in parsed.get_tags()
        if tag.name in {"nowiki", "pre", "code", "syntaxhighlight", "source", "math"}
    )
    ignored.extend(comment.span for comment in parsed.comments)
    expressions = []
    stack = []
    index = 0
    while index < len(text):
        if blocked := next((span for span in ignored if span[0] <= index < span[1]), None):
            index = blocked[1]
            continue
        if text.startswith("{{", index):
            stack.append(index)
            index += 2
        elif text.startswith("}}", index) and stack:
            start = stack.pop()
            index += 2
            if not stack and (node := nodes.get((start, index))) is not None:
                expressions.append(node)
        else:
            index += 1
    return expressions


class MagicRegistry:
    def __init__(self, query: dict, template_names=None):
        self.sensitive = {}
        self.insensitive = {}
        self.template_names = {name.casefold() for name in (template_names or {"Template"})}
        variables = set(query.get("variables", []))
        functions = set(query.get("functionhooks", []))
        for word in query.get("magicwords", []):
            name = word["name"]
            sensitive = "case-sensitive" in word and word["case-sensitive"] is not False
            mapping = self.sensitive if sensitive else self.insensitive
            for alias in word.get("aliases", []):
                has_colon = alias.endswith(":")
                alias = alias.removesuffix(":")
                key = alias if sensitive else alias.casefold()
                if name in variables and not has_colon:
                    mapping[(key, False, False)] = name
                if name in functions:
                    is_hash = not has_colon and name not in variables and name not in _COLON_FUNCTIONS
                    mapping[(key, is_hash, True)] = name

    def lookup(self, node) -> MagicCall | None:
        head, is_hash, has_colon = _head(node)
        if has_colon and not is_hash and head.casefold() in self.template_names:
            return None
        name = self.sensitive.get((head, is_hash, has_colon)) or self.insensitive.get(
            (head.casefold(), is_hash, has_colon)
        )
        if name is None:
            return None
        argument = str(node)[2:-2].partition(":")[2].split("|", 1)[0].strip() if has_colon else ""
        needs_page = name in _TITLE_VARIABLES and (not argument or "{{" in argument)
        return MagicCall(name=name, label=("#" if is_hash else "") + head, needs_page=needs_page)

    def validate(self, expression: str, page: str | None) -> MagicCall:
        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise MagicWordError("input_long")
        parsed = wtp.parse(expression)
        roots = extract_expressions(expression)
        if len(roots) != 1 or roots[0].span != (0, len(expression)):
            raise MagicWordError("invalid")
        if parsed.parameters or parsed.get_tags() or parsed.comments:
            raise MagicWordError("unsupported")
        nodes = [*parsed.templates, *parsed.parser_functions]
        if len(nodes) > MAX_EXPRESSION_NODES:
            raise MagicWordError("input_long")
        root_call = None
        for node in nodes:
            call = self.lookup(node)
            if call is None or call.name not in _SUPPORTED_WORDS:
                raise MagicWordError("unsupported")
            depth = sum(other.span[0] <= node.span[0] and node.span[1] <= other.span[1] for other in nodes)
            if depth > MAX_EXPRESSION_DEPTH:
                raise MagicWordError("input_long")
            if call.needs_page and not page:
                raise MagicWordError("page_required")
            if node.span == (0, len(expression)):
                root_call = call
        return root_call


async def get_registry(wiki: WikiLib) -> MagicRegistry:
    await wiki.fixup_wiki_info()
    record = _REGISTRY_CACHE[wiki.wiki_info.api]
    if (lock := record.get("lock")) is None:
        lock = asyncio.Lock()
        record["lock"] = lock
    async with lock:
        if (registry := record.get("registry")) is not None:
            return registry
        async with asyncio.timeout(MAGIC_TIMEOUT):
            response = await wiki.get_json(action="query", meta="siteinfo", siprop="magicwords|functionhooks|variables")
        query = response.get("query")
        if not isinstance(query, dict) or not all(
            isinstance(query.get(key), list) for key in ("magicwords", "functionhooks", "variables")
        ):
            raise InvalidWikiError(str(I18NContext("wiki.message.api.invalid_response")))
        template_names = {"Template"} | {name for name, ns in wiki.wiki_info.namespaces.items() if ns == 10}
        registry = MagicRegistry(query, template_names)
        record["registry"] = registry
        return registry


async def expand_magic(
    wiki: WikiLib,
    registry: MagicRegistry,
    expression: str,
    page: str | None = None,
    *,
    limit: int = MAX_RESULT_LENGTH,
    max_lines: int = 3,
) -> tuple[str, bool]:
    call = registry.validate(expression, page)
    params = {"action": "expandtemplates", "text": expression, "prop": "wikitext"}
    if page:
        params["title"] = page
    async with asyncio.timeout(MAGIC_TIMEOUT):
        response = await wiki.get_json(**params)
    if response.get("warnings"):
        raise MagicWordError("context_failed")
    expanded = response.get("expandtemplates")
    if not isinstance(expanded, dict) or not isinstance(expanded.get("wikitext"), str):
        raise InvalidWikiError(str(I18NContext("wiki.message.api.invalid_response")))
    result = expanded["wikitext"]
    result = result.strip()
    if len(result) > 16384:
        raise MagicWordError("output_long")
    soup = BeautifulSoup(result, "html.parser") if "<" in result else None
    if soup and soup.select(".error"):
        raise MagicWordError("evaluation_failed")
    if (soup and soup.find(True)) or any(marker in result for marker in ("{{", "[[", "{|")):
        raise MagicWordError("not_plain")
    if len(result) > limit or len(result.splitlines()) > max_lines:
        raise MagicWordError("output_long")
    is_url = call.name in _URL_FUNCTIONS or result.startswith(("http://", "https://", "//"))
    if is_url:
        result = urljoin(wiki.wiki_info.realurl, result)
        parsed_url = urlsplit(result)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or any(char.isspace() for char in result)
        ):
            raise MagicWordError("not_plain")
        if any(value not in {"view", "history", "raw"} for value in parse_qs(parsed_url.query).get("action", [])):
            raise MagicWordError("read_only_url")
        if len(result) > limit:
            raise MagicWordError("output_long")
    return result, is_url
