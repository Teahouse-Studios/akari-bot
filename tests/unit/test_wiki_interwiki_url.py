"""Wiki 全域及多级 Interwiki URL 解析回归测试。"""

from unittest.mock import AsyncMock, patch

from core.tester import func_case, Tester
from modules.wiki.utils.wikilib import WikiInfo, WikiLib, WikiStatus

SOURCE_API = "https://zh.minecraft.wiki/api.php"
TARGET_PAGE_URL = "https://meta.minecraft.wiki/w/Namespace_IDs?variant=zh-cn"
TARGET_API = "https://meta.minecraft.wiki/api.php"
TARGET_CURID_URL = "https://meta.minecraft.wiki/?curid=1614"
MIRAHEZE_SOURCE_API = "https://meta.miraheze.org/w/api.php"
MIRAHEZE_TARGET_PAGE_URL = "https://allthetropes.miraheze.org/wiki/Main_Page"
MIRAHEZE_TARGET_API = "https://allthetropes.org/w/api.php"
MIRAHEZE_TARGET_CURID_URL = "https://allthetropes.org/w/index.php?curid=58214"


async def _test_global_interwiki_uses_api_url():
    """Siteinfo 缺少全域前缀时，应使用查询响应中的 iwurl。"""
    source = WikiLib(SOURCE_API)
    source.wiki_info = WikiInfo(
        api=SOURCE_API,
        articlepath="https://zh.minecraft.wiki/w/$1",
        script="https://zh.minecraft.wiki/",
        interwiki={},
        in_allowlist=True,
    )
    captured = {}

    async def _check_wiki_available(self):
        captured["target_url"] = self.url
        return WikiStatus(
            available=True,
            value=WikiInfo(
                api=TARGET_API,
                articlepath="https://meta.minecraft.wiki/w/$1",
                script="https://meta.minecraft.wiki/",
                in_allowlist=True,
            ),
            message="",
        )

    async def _get_json(self, **kwargs):
        if self.wiki_info.api == SOURCE_API:
            captured["source_query"] = kwargs
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

    with (
        patch.object(WikiLib, "check_wiki_available", new=_check_wiki_available),
        patch.object(WikiLib, "get_json", new=_get_json),
        patch.object(WikiLib, "get_page_body_class", new=AsyncMock(return_value=[])),
    ):
        result = await source.parse_page_info("meta:Namespace IDs")

    return (
        captured["source_query"].get("iwurl") == "true"
        and source.wiki_info.interwiki == {}
        and captured["target_url"] == TARGET_PAGE_URL
        and result.status
        and result.id == 1614
        and result.title == "meta:Namespace IDs"
        and result.link == TARGET_CURID_URL
    )


async def _test_multilevel_interwiki_resolves_target_title():
    """多级前缀应从最终 URL 还原标题，并保留完整逻辑前缀。"""
    source = WikiLib(MIRAHEZE_SOURCE_API)
    source.wiki_info = WikiInfo(
        api=MIRAHEZE_SOURCE_API,
        articlepath="https://meta.miraheze.org/wiki/$1",
        script="https://meta.miraheze.org/w/index.php",
        interwiki={"mh": "https://meta.miraheze.org/wiki/$1"},
        in_allowlist=True,
    )
    captured = {}

    async def _check_wiki_available(self):
        captured["target_url"] = self.url
        return WikiStatus(
            available=True,
            value=WikiInfo(
                api=MIRAHEZE_TARGET_API,
                articlepath="https://allthetropes.org/wiki/$1",
                script="https://allthetropes.org/w/index.php",
                in_allowlist=True,
            ),
            message="",
        )

    async def _get_json(self, **kwargs):
        if self.wiki_info.api == MIRAHEZE_SOURCE_API:
            captured["source_query"] = kwargs
            return {
                "query": {
                    "interwiki": [
                        {
                            "title": "mh:allthetropes:Main Page",
                            "iw": "mh",
                            "url": MIRAHEZE_TARGET_PAGE_URL,
                        }
                    ]
                }
            }
        captured["target_query"] = kwargs
        return {
            "query": {
                "pages": {
                    "58214": {
                        "pageid": 58214,
                        "ns": 0,
                        "title": "Main Page",
                        "fullurl": "https://allthetropes.org/wiki/Main_Page",
                    }
                }
            }
        }

    with (
        patch.object(WikiLib, "check_wiki_available", new=_check_wiki_available),
        patch.object(WikiLib, "get_json", new=_get_json),
        patch.object(WikiLib, "get_page_body_class", new=AsyncMock(return_value=[])),
    ):
        result = await source.parse_page_info("mh:allthetropes:Main_Page")

    return (
        captured["source_query"].get("iwurl") == "true"
        and captured["target_url"] == MIRAHEZE_TARGET_PAGE_URL
        and captured["target_query"].get("titles") == "Main Page"
        and result.status
        and result.id == 58214
        and result.title == "mh:allthetropes:Main Page"
        and result.link == MIRAHEZE_TARGET_CURID_URL
    )


@func_case
async def test_wiki_interwiki_url(tester: Tester):
    """wiki: 使用 API 解析全域及多级 Interwiki"""
    await tester.test(_test_global_interwiki_uses_api_url, "全域 Interwiki 使用 iwurl 返回的目标地址")
    await tester.test(_test_multilevel_interwiki_resolves_target_title, "多级 Interwiki 发现目标 API 并还原标题")
    return tester
