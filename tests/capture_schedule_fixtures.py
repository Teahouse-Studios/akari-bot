"""定时任务语料捕获工具。

定时任务不经由消息解析触发，普通的集成测试录制流程覆盖不到它们依赖的外部请求。
此脚本直接触发各模块的 schedule 函数，把途中的 HTTP 响应与 WebRender 取源结果
分别录入 tests/fixtures/http/ 与 tests/fixtures/webrender/。

WebRender 依赖无头浏览器，录制阶段无法真正渲染，故以普通 HTTP 抓取同一 URL 的
响应代替。对必须执行脚本才能出内容的页面，抓取结果与真实渲染并不等价，此时应改为
手工编写最小语料。

使用方式：
    python tests/capture_schedule_fixtures.py                  # 录制全部可录制的任务
    python tests/capture_schedule_fixtures.py arcaea_rss ...   # 只录制指定模块
"""

import asyncio
import json
import sys

sys.path.insert(0, ".")

from core.tester.mock.database import init_db, close_db
from core.tester.mock.fixtures import save_fixture
from core.tester.mock.http import digest_request_body
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.mock.scheduler import get_scheduled_tasks
from core.tester.mock.webrender import save_webrender_fixture

# 这些模块的定时任务无法在录制环境中产生有效语料，跳过以免徒劳等待。
SKIPPED = {
    # 多页抓取叠加图片渲染，单次运行耗时过长，不适合纳入测试。
    "weekly_rss": "抓取页数多且需图片渲染，耗时过长",
    # 依赖 Google Play 抓取，且在 ip_country 未配置时直接早退。
    "mcbv_rss": "依赖 Google Play 抓取，测试环境直接早退",
    # 需要真实 wiki 机器人账号凭据。
    "wiki_bot": "需要真实 wiki 账号凭据",
}

_http: dict[tuple, dict] = {}
_render: dict[str, str] = {}


def _normalize(result):
    if isinstance(result, bytes):
        return "", None, result
    if isinstance(result, str):
        return result, None, b""
    try:
        return json.dumps(result, ensure_ascii=False), result, b""
    except (TypeError, ValueError):
        return str(result), None, b""


async def main():
    wanted = sys.argv[1:]

    print("=" * 60)
    print("Schedule Fixture Capture Tool")
    print("=" * 60)

    await init_db()
    await load_modules(show_logs=False, monkey_patches={"Random": Random()}, load_fixtures=False)

    import core.utils.http as http_module
    from core.web_render import web_render

    original_request = http_module.request_url
    original_source = web_render.source

    async def capturing_request(url, method="GET", **kwargs):
        result = await original_request(url, method=method, **kwargs)
        body = kwargs.get("data")
        text, json_data, content = _normalize(result)
        _http[(url, method.upper(), digest_request_body(body))] = {
            "url": url,
            "method": method,
            "status_code": kwargs.get("status_code") or 200,
            "text": text,
            "json_data": json_data,
            "content": content,
            "request_body": body,
        }
        print(f"    http   [{method}] {url[:90]} ({len(content) or len(text)} bytes)")
        return result

    async def capturing_source(options, *args, **kwargs):
        url = getattr(options, "url", None)
        if not url:
            return None
        try:
            text = await original_request(url, method="GET", timeout=30, attempt=1, logging_err_resp=False)
        except Exception as e:
            print(f"    render FAIL {url[:80]} -> {type(e).__name__}")
            return None
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        _render[url] = text
        print(f"    render {url[:90]} ({len(text)} chars)")
        return text

    http_module.request_url = capturing_request
    web_render.source = capturing_source

    try:
        for task in get_scheduled_tasks():
            name = task["module_name"]
            if wanted and name not in wanted:
                continue
            if name in SKIPPED:
                print(f"\n>> {name}: SKIPPED ({SKIPPED[name]})")
                continue
            print(f"\n>> {name}")
            try:
                await asyncio.wait_for(task["function"](), timeout=120)
            except asyncio.TimeoutError:
                print("    task timed out")
            except Exception as e:
                print(f"    task raised {type(e).__name__}: {str(e)[:70]}")
    finally:
        http_module.request_url = original_request
        web_render.source = original_source

    print(f"\n{'=' * 60}")
    for item in _http.values():
        save_fixture(
            url=item["url"],
            status_code=item["status_code"],
            text=item["text"],
            content=item["content"],
            json_data=item["json_data"],
            method=item["method"],
            request_body=item["request_body"],
        )
    for url, text in _render.items():
        save_webrender_fixture(url, text)

    print(f"Saved {len(_http)} HTTP fixtures and {len(_render)} WebRender fixtures")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
