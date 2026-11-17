import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup, Comment
from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.builtins.message.internal import I18NContext


_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    autoescape=select_autoescape(["html"]),
)


class DiffError(ValueError):
    pass


def parse_diff_target(value: str, wiki_info) -> dict | None:
    value = value.strip()
    is_url = value.startswith(("https://", "http://"))
    if is_url:
        parts = urlsplit(value)
        query = parse_qs(parts.query, keep_blank_values=True)
        title = query.get("title", [""])[0]
        article_path = urlsplit(wiki_info.articlepath).path
        if not title and "$1" in article_path:
            before, after = article_path.split("$1", 1)
            if parts.path.startswith(before) and parts.path.endswith(after):
                title = unquote(parts.path[len(before) : len(parts.path) - len(after) if after else None])
    else:
        value = value.split("#", 1)[0]
        parts = re.split(r"[?&](?=(?:diff|oldid|curid|variant|title)=)", value, maxsplit=1)
        title = parts[0]
        query = parse_qs(parts[1], keep_blank_values=True) if len(parts) == 2 else {}

    special = re.fullmatch(r"([^:]+):([^/]+)(?:/(.*))?", title, re.I)
    is_special = (
        special
        and (
            special[1].lower() in {"special", "特殊"}
            or any(name.casefold() == special[1].casefold() and ns == -1 for name, ns in wiki_info.namespaces.items())
        )
        and special[2].casefold() in {"diff", "差异", "差異"}
    )
    if "diff" not in query and not is_special:
        return None
    if any(len(values) != 1 for key, values in query.items() if key in {"diff", "oldid", "curid", "variant"}):
        raise DiffError("wiki.message.diff.invalid")

    def revision(value):
        if not re.fullmatch(r"[0-9]+", value or "") or int(value) <= 0:
            raise DiffError("wiki.message.diff.invalid")
        return int(value)

    diff = query.get("diff", [None])[0]
    oldid = query.get("oldid", [None])[0]
    if oldid == "0":
        oldid = None
    if diff is None:
        revisions = (special[3] or "").split("/")
        if len(revisions) == 1:
            diff = revisions[0]
        elif len(revisions) == 2:
            oldid, diff = revisions
        else:
            raise DiffError("wiki.message.diff.invalid")
    diff = diff.lower()
    if diff in {"prev", "next", "cur", "0"}:
        relative = "cur" if diff == "0" else diff
        if oldid:
            target = {"fromrev": revision(oldid), "torelative": relative}
        elif relative == "cur":
            # 没有指定旧版本时，网页比较当前版本与它的上一版。
            target = {"torelative": "prev"}
            if pageid := query.get("curid", [None])[0]:
                target["fromid"] = revision(pageid)
            elif title and not is_special and (not is_url or "title" in query or urlsplit(value).path != "/"):
                target["fromtitle"] = title
            else:
                raise DiffError("wiki.message.diff.invalid")
        else:
            raise DiffError("wiki.message.diff.invalid")
    elif oldid:
        target = {"fromrev": revision(oldid), "torev": revision(diff)}
    else:
        target = {"fromrev": revision(diff), "torelative": "prev"}
    if variant := query.get("variant", [None])[0]:
        target["uselang"] = variant
    return target


async def fetch_diff(wiki, target: dict) -> dict:
    response = await wiki.get_json(
        action="compare", prop="diff|ids|title|user|timestamp|comment", formatversion=2, **target
    )
    data = response.get("compare")
    if response.get("error") or not isinstance(data, dict):
        raise DiffError("wiki.message.diff.unavailable")
    body = data.get("body", data.get("*"))
    if not isinstance(body, str) or not data.get("torevid") or "fromrevid" not in data:
        raise DiffError("wiki.message.diff.unavailable")
    return {**data, "body": body}


def _sanitize_diff(body: str) -> str:
    soup = BeautifulSoup(body, "html.parser")
    for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()
    for tag in list(soup.find_all(True)):
        if tag.name in {"script", "style", "iframe", "object", "embed", "svg", "math"}:
            tag.decompose()
    for tag in list(soup.find_all(True)):
        if tag.name not in {"tr", "td", "th", "div", "span", "ins", "del", "br", "bdi"}:
            tag.unwrap()
            continue
        attrs = {}
        if classes := [name for name in tag.get("class", []) if re.fullmatch(r"diff[-\w]*", name)]:
            attrs["class"] = classes
        if tag.get("colspan") in {"1", "2", "4"}:
            attrs["colspan"] = tag["colspan"]
        if tag.get("data-marker") in {"+", "−", "-"}:
            attrs["data-marker"] = tag["data-marker"]
        tag.attrs = attrs
    return str(soup)


def diff_document(data: dict, site_name: str, locale) -> str:
    def text(key, **kwargs):
        context = I18NContext("wiki.message.diff." + key, **kwargs)
        return locale.t(context.key, **context.kwargs)

    def revision(side):
        return text("revision", revision=data.get(side + "revid", ""))

    def metadata(side):
        return " · ".join(str(data.get(side + key, "")) for key in ("timestamp", "user"))

    body = _sanitize_diff(data["body"])
    return _TEMPLATE_ENV.get_template("diff.html").render(
        heading=text("heading"),
        site=site_name,
        from_title=data.get("fromtitle", ""),
        to_title=data.get("totitle", ""),
        from_revision=revision("from"),
        to_revision=revision("to"),
        from_meta=metadata("from"),
        to_meta=metadata("to"),
        from_comment=data.get("fromcomment", ""),
        to_comment=data.get("tocomment", ""),
        body=body,
        has_body=bool(body.strip()),
        empty=text("empty"),
    )
