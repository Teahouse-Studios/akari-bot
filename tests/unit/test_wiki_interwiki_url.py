"""Wiki 全域 Interwiki URL 解析回归测试。"""

from unittest.mock import AsyncMock, patch

from core.tester import func_case, Tester
from modules.wiki.utils.wikilib import WikiInfo, WikiLib, WikiStatus

SOURCE_API = "https://zh.minecraft.wiki/api.php"
TARGET_PAGE_URL = "https://meta.minecraft.wiki/w/Namespace_IDs?variant=zh-cn"
TARGET_API = "https://meta.minecraft.wiki/api.php"
TARGET_CURID_URL = "https://meta.minecraft.wiki/?curid=1614"


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


@func_case
async def test_wiki_interwiki_url(tester: Tester):
    """wiki: 使用 API 解析不在 Siteinfo 中的全域 Interwiki"""
    await tester.test(_test_global_interwiki_uses_api_url, "全域 Interwiki 使用 iwurl 返回的目标地址")
    return tester
