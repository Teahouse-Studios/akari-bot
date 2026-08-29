"""Wiki 站点信息缓存异常响应回归测试。"""

from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.tester import func_case, Tester
from core.utils.url_policy import URLPolicyDecision
from modules.wiki.utils.wikilib import BlockedWikiError, WikiInfo, WikiLib

API_LINK = "https://example.com/api.php"
PAGE_LINK = "https://example.com/wiki/Example_Page"
PAGE_API_LINK = "https://example.com/w/api.php"
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


async def _test_page_url_resolves_edituri_api():
    cache = _cache({})
    page_html = (
        f'<html><head><link rel="EditURI" type="application/rsd+xml" href="{PAGE_API_LINK}?action=rsd"></head></html>'
    )
    get_url = AsyncMock(return_value=page_html)
    get_json = AsyncMock(return_value=VALID_SITEINFO)
    with (
        patch("modules.wiki.utils.wikilib.get_url", new=get_url),
        patch("modules.wiki.utils.wikilib.WikiSiteInfo.get_or_none", new=AsyncMock(return_value=None)),
        patch("modules.wiki.utils.wikilib.WikiSiteInfo.create", new=AsyncMock(return_value=cache)),
        patch.object(WikiLib, "get_json_from_api", new=get_json),
        patch(
            "modules.wiki.utils.wikilib.evaluate_url_policy",
            return_value=URLPolicyDecision(allowed=False, blocked=False),
        ),
    ):
        result = await WikiLib(PAGE_LINK).check_wiki_available()

    return (
        result.available
        and result.value.api == PAGE_API_LINK
        and get_url.await_args.args == (PAGE_LINK,)
        and get_json.await_args.args == (PAGE_API_LINK,)
        and cache.save.await_count == 1
    )


async def _test_invalid_cache_is_refetched():
    cache = _cache(ERROR_SITEINFO)
    with (
        patch("modules.wiki.utils.wikilib.WikiSiteInfo.get_or_none", new=AsyncMock(return_value=cache)),
        patch.object(WikiLib, "get_json_from_api", new=AsyncMock(return_value=VALID_SITEINFO)) as get_json,
        patch(
            "modules.wiki.utils.wikilib.evaluate_url_policy",
            return_value=URLPolicyDecision(allowed=False, blocked=False),
        ),
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
        patch(
            "modules.wiki.utils.wikilib.evaluate_url_policy",
            return_value=URLPolicyDecision(allowed=False, blocked=False),
        ),
    ):
        result = await WikiLib(API_LINK).check_wiki_available()

    return not result.available and "maxlag" in result.message and cache.site_info == {} and cache.save.await_count == 0


async def _test_siteinfo_uses_global_url_policy():
    with patch(
        "modules.wiki.utils.wikilib.evaluate_url_policy",
        return_value=URLPolicyDecision(allowed=True, blocked=False),
    ) as evaluate:
        result = await WikiLib(API_LINK).rearrange_siteinfo(VALID_SITEINFO, API_LINK)

    return (
        result.is_allowed
        and not result.is_blocked
        and evaluate.call_count == 1
        and evaluate.call_args.args == (API_LINK,)
    )


async def _test_blocklisted_wiki_skips_network_requests():
    get_url = AsyncMock()
    get_json = AsyncMock()
    with (
        patch(
            "modules.wiki.utils.wikilib.evaluate_url_policy",
            return_value=URLPolicyDecision(allowed=False, blocked=True),
        ),
        patch("modules.wiki.utils.wikilib.get_url", new=get_url),
        patch.object(WikiLib, "get_json_from_api", new=get_json),
    ):
        try:
            await WikiLib(API_LINK).check_wiki_available()
        except BlockedWikiError:
            pass
        else:
            return False
    return get_url.await_count == 0 and get_json.await_count == 0


async def _test_bound_wiki_is_rechecked_before_content_request():
    wiki = WikiLib(API_LINK)
    wiki.wiki_info = WikiInfo(api=API_LINK)
    get_json = AsyncMock()
    with (
        patch(
            "modules.wiki.utils.wikilib.evaluate_url_policy",
            return_value=URLPolicyDecision(allowed=False, blocked=True),
        ),
        patch.object(WikiLib, "get_json_from_api", new=get_json),
    ):
        try:
            await wiki.get_json(action="query", meta="siteinfo")
        except BlockedWikiError:
            pass
        else:
            return False
    return get_json.await_count == 0


@func_case
async def test_wiki_siteinfo_cache(tester: Tester):
    """wiki: 无效站点信息缓存与 API 响应处理"""
    await tester.test(_test_page_url_resolves_edituri_api, "Wiki 页面地址应通过 EditURI 解析 API URL")
    await tester.test(_test_invalid_cache_is_refetched, "无效缓存会失效并重新请求")
    await tester.test(_test_invalid_response_is_not_cached, "无效 API 响应不会写入缓存")
    await tester.test(_test_siteinfo_uses_global_url_policy, "Wiki 站点信息以规范 API 端点查询全局 URL 策略")
    await tester.test(_test_blocklisted_wiki_skips_network_requests, "阻止列表中的 Wiki 不发起站点探测或 API 请求")
    await tester.test(_test_bound_wiki_is_rechecked_before_content_request, "已绑定 Wiki 在内容请求前重新检查阻止列表")
    return tester
