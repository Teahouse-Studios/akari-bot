import asyncio
import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bs4 import BeautifulSoup
from PIL import Image

from core.i18n import Locale
from core.tester import Tester, func_case
from modules.wiki.utils.diff import DiffError, diff_document, fetch_diff, parse_diff_target
from modules.wiki.utils.screenshot_image import generate_screenshot
from modules.wiki.utils.wikilib import WikiInfo, WikiLib

API = "https://zh.minecraft.wiki/api.php"
SINGLE = "https://zh.minecraft.wiki/w/Special:Diff/1495502"
PAIR = "https://zh.minecraft.wiki/w/%E5%88%BB?curid=7766&diff=1500031&oldid=1476854"


def _info():
    return WikiInfo(
        api=API,
        script="https://zh.minecraft.wiki/",
        articlepath="https://zh.minecraft.wiki/w/$1",
        name="Minecraft Wiki",
        is_allowed=True,
    )


def _data():
    return {
        "fromrevid": 1476854,
        "torevid": 1500031,
        "fromtitle": "刻",
        "totitle": "刻",
        "fromuser": "编辑者 A",
        "touser": "编辑者 B",
        "totimestamp": "2026-10-04T16:31:13Z",
        "body": '<tr><td class="diff-marker" data-marker="−"></td><td class="diff-deletedline"><div>'
        '<del class="diffchange">旧内容</del></div></td><td class="diff-marker" data-marker="+"></td>'
        '<td class="diff-addedline"><div><ins class="diffchange">新内容</ins></div></td></tr>',
    }


def _test_targets():
    info = _info()
    for value in [
        "Special:Diff/1495502",
        "special:diff/1495502",
        "特殊:差异/1495502",
        SINGLE,
        "https://zh.minecraft.wiki/?diff=1495502&variant=zh-cn",
        "https://zh.minecraft.wiki/index.php?title=Special%3ADiff%2F1495502",
    ]:
        result = parse_diff_target(value, info)
        assert result["fromrev"] == 1495502 and result["torelative"] == "prev", value
    for value in [
        PAIR,
        "刻&diff=1500031&oldid=1476854",
        "刻?oldid=1476854&diff=1500031",
        "Special:Diff/1476854/1500031",
        "https://zh.minecraft.wiki/w/Special:Diff/1476854/1500031",
    ]:
        assert parse_diff_target(value, info) == {"fromrev": 1476854, "torev": 1500031}, value
    for relative in ["prev", "next", "cur"]:
        assert parse_diff_target(f"刻?oldid=12&diff={relative}", info) == {"fromrev": 12, "torelative": relative}
    for value in ["刻", "Special:RecentChanges", "刻?oldid=12", "A&B", "刻#diff=12"]:
        assert parse_diff_target(value, info) is None, value
    for value in [
        "Special:Diff/no",
        "Special:Diff/1/2/3",
        "刻?diff=bad",
        "刻?diff=12&oldid=bad",
        "刻?diff=1&diff=2",
        "Special:Diff",
        "刻?diff=next",
    ]:
        try:
            parse_diff_target(value, info)
        except DiffError:
            pass
        else:
            raise AssertionError(value)
    return True


async def _test_page_info():
    wiki = WikiLib(API)
    wiki.wiki_info = _info()
    for value in ["Special:Diff/1495502", PAIR, "刻&diff=1500031&oldid=1476854"]:
        with patch.object(WikiLib, "get_json", new=AsyncMock(return_value={"compare": _data()})) as request:
            result = await wiki.parse_page_info(value, inline=True, check_render=True)
        assert result.status and result.renderable and result.diff_data == _data()
        assert result.title == "刻" and result.link == "https://zh.minecraft.wiki/?oldid=1476854&diff=1500031"
        assert request.await_count == 1 and request.await_args.kwargs["action"] == "compare"
    for response in [{"error": {"code": "nosuchrevid"}}, {"compare": {"fromrevid": 1, "torevid": 2}}]:
        with patch.object(WikiLib, "get_json", new=AsyncMock(return_value=response)):
            result = await wiki.parse_page_info("Special:Diff/1495502")
        assert not result.status and not result.renderable and "wiki.message.diff.unavailable" in result.desc
    with patch.object(WikiLib, "get_json", new=AsyncMock()) as request:
        result = await wiki.parse_page_info("刻?diff=bad")
    assert not result.status and not request.await_count and "wiki.message.diff.invalid" in result.desc
    with patch.object(WikiLib, "get_json", new=AsyncMock(side_effect=asyncio.CancelledError())):
        try:
            await wiki.parse_page_info("Special:Diff/1495502")
        except asyncio.CancelledError:
            pass
        else:
            return False
    return True


def _test_document():
    data = _data()
    data["totitle"] = '<img src="https://example.org/test">'
    data["tocomment"] = "<script>alert(1)</script>"
    data["fromcomment"] = '<b>A & B</b> {{7*7}} "quoted"'
    data["fromuser"] = "A & B"
    data["body"] += '<script>alert(1)</script><img src="https://example.org/test"><tr><td onclick="bad()" '
    data["body"] += 'style="background:url(https://example.org/test)"><a href="https://example.org">link</a></td></tr>'
    document = diff_document(data, "Minecraft & Wiki", Locale("zh_cn"))
    soup = BeautifulSoup(document, "html.parser")
    assert not soup.find(["script", "img", "a", "link"])
    assert not soup.select("[onclick], [src], [href]")
    assert soup.select_one(".diff-addedline ins.diffchange").text == "新内容"
    assert "版本差异" in soup.text and "版本 1500031" in soup.text
    assert "<script>alert(1)</script>" in soup.text
    assert soup.select_one(".site").text == "Minecraft & Wiki"
    assert soup.select_one(".comment").text == data["fromcomment"]
    assert soup.select_one(".meta").text == " · A & B"
    assert "default-src 'none'" in document
    assert "没有内容差异" in diff_document({**data, "body": ""}, "Wiki", Locale("zh_cn"))
    return True


async def _test_render():
    buffer = BytesIO()
    Image.new("RGB", (2, 2)).save(buffer, "PNG")
    images = [base64.b64encode(buffer.getvalue()).decode()]
    with (
        patch.object(WikiLib, "get_json", new=AsyncMock(return_value={"compare": _data()})) as request,
        patch(
            "modules.wiki.utils.screenshot_image.web_render.element_screenshot", new=AsyncMock(return_value=images)
        ) as render,
        patch("modules.wiki.utils.screenshot_image.generate_screenshot_v2", new=AsyncMock()) as fallback,
    ):
        result = await generate_screenshot(PAIR, _info(), allow_special_page=True)
        assert result and result[0].size == (2, 2)
        assert request.await_count == 1 and request.await_args.kwargs["fromrev"] == 1476854
        options = render.await_args.args[0]
        assert options.url is None and options.width == 1200 and "新内容" in options.content
        await generate_screenshot(PAIR, _info(), allow_special_page=True, diff_data=_data())
        assert request.await_count == 1
        assert not await generate_screenshot(PAIR, _info())
        request.side_effect = RuntimeError("unavailable")
        assert not await generate_screenshot(PAIR, _info(), allow_special_page=True)
        assert not fallback.await_count
    return True


async def _test_hidden_and_empty():
    wiki = SimpleNamespace(get_json=AsyncMock(return_value={"compare": {**_data(), "body": ""}}))
    assert (await fetch_diff(wiki, {"fromrev": 1, "torelative": "prev"}))["body"] == ""
    wiki.get_json.return_value = {"compare": {"fromrevid": 1, "torevid": 2, "fromtexthidden": True}}
    try:
        await fetch_diff(wiki, {"fromrev": 1, "torelative": "prev"})
    except DiffError:
        return True
    return False


@func_case
async def test_wiki_diff(tester: Tester):
    await tester.test(_test_targets, "差异标题、查询参数和 URL 统一解析，并拒绝无效参数")
    await tester.test(_test_page_info, "差异直接走 compare，固定版本链接、预览状态及错误提示正确")
    await tester.test(_test_document, "本地模板保留差异高亮、转义元数据并移除远程资源和脚本")
    await tester.test(_test_render, "仅渲染本地内容，复用 compare 响应且失败不请求页面")
    await tester.test(_test_hidden_and_empty, "区分无差异与隐藏内容")
    return tester
