"""Wiki 站点信息缓存异常响应回归测试。"""

from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.tester import func_case, Tester
from modules.wiki.utils.wikilib import WikiLib

API_LINK = "https://example.com/api.php"
VALID_SITEINFO = {
    "query": {
        "extensions": [{"name": "TextExtracts"}],
        "general": {
            "server": "https://example.com",
            "articlepath": "/wiki/$1",
            "sitename": "Example Wiki",
            "script": "/w/index.php",
        },
        "namespaces": {},
        "namespacealiases": [],
        "interwikimap": [],
    }
}
ERROR_SITEINFO = {"error": {"code": "maxlag", "info": "Waiting for replication lag to decrease."}}


def _cache(site_info):
    return SimpleNamespace(site_info=site_info, timestamp=datetime.now(UTC), save=AsyncMock())


async def _test_invalid_cache_is_refetched():
    cache = _cache(ERROR_SITEINFO)
    with (
        patch("modules.wiki.utils.wikilib.WikiSiteInfo.get_or_none", new=AsyncMock(return_value=cache)),
        patch.object(WikiLib, "get_json_from_api", new=AsyncMock(return_value=VALID_SITEINFO)) as get_json,
        patch("modules.wiki.utils.wikilib.WikiAllowList.check", new=AsyncMock(return_value=False)),
        patch("modules.wiki.utils.wikilib.WikiBlockList.check", new=AsyncMock(return_value=False)),
    ):
        result = await WikiLib(API_LINK).check_wiki_available()

    return (
        result.available
        and result.value.name == "Example Wiki"
        and get_json.await_count == 1
        and cache.site_info == VALID_SITEINFO
        and cache.save.await_count == 2
    )


async def _test_invalid_response_is_not_cached():
    cache = _cache({})
    with (
        patch("modules.wiki.utils.wikilib.WikiSiteInfo.get_or_none", new=AsyncMock(return_value=cache)),
        patch.object(WikiLib, "get_json_from_api", new=AsyncMock(return_value=ERROR_SITEINFO)),
    ):
        result = await WikiLib(API_LINK).check_wiki_available()

    return not result.available and "maxlag" in result.message and cache.site_info == {} and cache.save.await_count == 0


@func_case
async def test_wiki_siteinfo_cache(tester: Tester):
    """wiki: 无效站点信息缓存与 API 响应处理"""
    await tester.test(_test_invalid_cache_is_refetched, "无效缓存会失效并重新请求")
    await tester.test(_test_invalid_response_is_not_cached, "无效 API 响应不会写入缓存")
    return tester
