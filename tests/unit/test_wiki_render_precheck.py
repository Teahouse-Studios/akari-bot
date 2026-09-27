"""Wiki WebRender 预检查在跨 wiki 跳转后的传递测试。"""

from unittest.mock import AsyncMock, patch

from core.tester import func_case, Tester
from modules.wiki.utils.wikilib import WikiInfo, WikiLib, WikiStatus

SOURCE_API = "https://zh.minecraft.wiki/api.php"
SOURCE_ARTICLE_PATH = "https://zh.minecraft.wiki/w/$1"
TARGET_API = "https://meta.minecraft.wiki/api.php"
TARGET_ARTICLE_PATH = "https://meta.minecraft.wiki/w/$1"
TARGET_PAGE_URL = "https://meta.minecraft.wiki/w/Namespace_IDs"
TARGET_CURID_URL = "https://meta.minecraft.wiki/?curid=1614"
EN_API = "https://en.minecraft.wiki/api.php"
EN_ARTICLE_PATH = "https://en.minecraft.wiki/wiki/$1"
EN_PAGE_URL = "https://en.minecraft.wiki/wiki/Example_Page"
EN_CURID_URL = "https://en.minecraft.wiki/?curid=2"


def _source_wiki(interwiki: dict[str, str]) -> WikiLib:
    source = WikiLib(SOURCE_API)
    source.wiki_info = WikiInfo(
        api=SOURCE_API,
        articlepath=SOURCE_ARTICLE_PATH,
        script="https://zh.minecraft.wiki/",
        interwiki=interwiki,
        is_allowed=True,
    )
    return source


def _target_wiki_info(api: str, articlepath: str, script: str) -> WikiInfo:
    return WikiInfo(
        api=api,
        articlepath=articlepath,
        script=script,
        is_allowed=True,
    )


async def _test_interwiki_checks_renderable_on_target_wiki():
    source = _source_wiki({})
    captured = {}

    async def _check_wiki_available(self):
        return WikiStatus(
            available=True,
            value=_target_wiki_info(TARGET_API, TARGET_ARTICLE_PATH, "https://meta.minecraft.wiki/"),
            message="",
        )

    async def _get_json(self, **kwargs):
        if self.wiki_info.api == SOURCE_API:
            return {
                "query": {
                    "interwiki": [
                        {
                            "title": "meta:Namespace IDs",
                            "iw": "meta",
                            "url": TARGET_PAGE_URL,
                        }
                    ]
                }
            }
        return {
            "query": {
                "pages": {
                    "1614": {
                        "pageid": 1614,
                        "ns": 0,
                        "title": "Namespace IDs",
                        "fullurl": "https://meta.minecraft.wiki/w/Namespace_IDs",
                    }
                }
            }
        }

    async def _check_page_renderable(self, page_name, *, content_mode=False):
        captured["render_target"] = (self.wiki_info.api, page_name, content_mode)
        return True

    with (
        patch.object(WikiLib, "check_wiki_available", new=_check_wiki_available),
        patch.object(WikiLib, "get_json", new=_get_json),
        patch.object(WikiLib, "get_page_body_class", new=AsyncMock(return_value=[])),
        patch.object(WikiLib, "check_page_renderable", new=_check_page_renderable),
    ):
        result = await source.parse_page_info("meta:Namespace IDs", check_render=True)

    return (
        result.status
        and result.link == TARGET_CURID_URL
        and captured.get("render_target") == (TARGET_API, "Namespace IDs", False)
        and result.renderable is True
    )


async def _test_langlinks_checks_renderable_on_target_wiki():
    source = _source_wiki({"en": EN_ARTICLE_PATH})
    captured = {}

    async def _check_wiki_available(self):
        return WikiStatus(
            available=True,
            value=_target_wiki_info(EN_API, EN_ARTICLE_PATH, "https://en.minecraft.wiki/"),
            message="",
        )

    async def _get_json(self, **kwargs):
        if self.wiki_info.api == SOURCE_API:
            return {
                "query": {
                    "pages": {
                        "1": {
                            "pageid": 1,
                            "ns": 0,
                            "title": "示例页面",
                            "fullurl": "https://zh.minecraft.wiki/w/示例页面",
                            "langlinks": [{"lang": "en", "url": EN_PAGE_URL, "*": "Example Page"}],
                        }
                    }
                }
            }
        return {
            "query": {
                "pages": {
                    "2": {
                        "pageid": 2,
                        "ns": 0,
                        "title": "Example Page",
                        "fullurl": EN_PAGE_URL,
                    }
                }
            }
        }

    async def _check_page_renderable(self, page_name, *, content_mode=False):
        captured["render_target"] = (self.wiki_info.api, page_name, content_mode)
        return True

    with (
        patch.object(WikiLib, "check_wiki_available", new=_check_wiki_available),
        patch.object(WikiLib, "get_json", new=_get_json),
        patch.object(WikiLib, "get_page_body_class", new=AsyncMock(return_value=[])),
        patch.object(WikiLib, "check_page_renderable", new=_check_page_renderable),
    ):
        result = await source.parse_page_info("示例页面", lang="en", check_render=True)

    return (
        result.status
        and result.link == EN_CURID_URL
        and captured.get("render_target") == (EN_API, "Example Page", False)
        and result.renderable is True
    )


@func_case
async def test_wiki_render_precheck(tester: Tester):
    """wiki: 跨 wiki 跳转后仍判定目标页面可渲染性"""
    await tester.test(_test_interwiki_checks_renderable_on_target_wiki, "Interwiki 跳转后在目标 wiki 上判定可渲染性")
    await tester.test(_test_langlinks_checks_renderable_on_target_wiki, "语言版本跳转后在目标 wiki 上判定可渲染性")
    return tester
