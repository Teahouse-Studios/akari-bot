"""HTTP Fixture 捕获工具 - 运行测试并记录所有 HTTP 响应到本地文件。

使用方式：
    python tests/capture_http_fixtures.py

脚本会：
    1. 启动测试环境
    2. 为 request_url 添加拦截器，记录所有 HTTP 请求和响应
    3. 运行集成测试（test_external_modules 等）
    4. 将所有捕获的响应保存到 tests/fixtures/http/

之后运行 tester.py 时，fixture 会自动加载，HTTP 请求被 mock 拦截。
"""

import asyncio
import json
import sys

sys.path.insert(0, ".")

from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.mock.fixtures import save_fixture, FIXTURE_DIR

_captured: list[dict] = []


async def main():
    print("=" * 60)
    print("HTTP Fixture Capture Tool")
    print("=" * 60)

    await init_db()
    await load_modules(show_logs=False, monkey_patches={"Random": Random()})

    import core.utils.http as http_module

    original_request_url = http_module.request_url
    original_get_url = http_module.get_url
    original_post_url = http_module.post_url

    async def capturing_request_url(url, method="GET", **kwargs):
        try:
            result = await original_request_url(url, method=method, **kwargs)
            if isinstance(result, str):
                text = result
                json_data = None
            else:
                text = json.dumps(result, ensure_ascii=False)
                json_data = result
            _captured.append(
                {
                    "url": url,
                    "method": method,
                    "status_code": 200,
                    "text": text,
                    "json_data": json_data,
                }
            )
            print(f"  CAPTURED: [{method}] {url} -> 200 ({len(text)} chars)")
            return result
        except Exception as e:
            print(f"  ERROR: [{method}] {url} -> {type(e).__name__}: {e}")
            raise

    async def capturing_get_url(url, **kwargs):
        return await capturing_request_url(url, method="GET", **kwargs)

    async def capturing_post_url(url, data=None, **kwargs):
        return await capturing_request_url(url, method="POST", data=data, **kwargs)

    http_module.request_url = capturing_request_url
    http_module.get_url = capturing_get_url
    http_module.post_url = capturing_post_url

    print("\n--- Running integration tests ---\n")

    test_modules = [
        "tests.integration.test_external_modules",
        "tests.integration.test_more_external_modules",
        "tests.integration.test_more_modules",
        "tests.integration.test_utility_modules",
    ]

    for module_name in test_modules:
        print(f"\n>> Loading {module_name}")
        try:
            mod = __import__(module_name, fromlist=["*"])
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if callable(attr) and getattr(attr, "_func_case", False):
                    from core.tester.tester import Tester

                    print(f"\n  Running: {attr_name}")
                    tester = Tester(attr_name)
                    try:
                        await attr(tester)
                    except Exception as e:
                        print(f"  FAILED: {e}")
        except Exception as e:
            print(f"  Module load error: {e}")

    http_module.request_url = original_request_url
    http_module.get_url = original_get_url
    http_module.post_url = original_post_url

    print(f"\n{'=' * 60}")
    print(f"Captured {len(_captured)} HTTP responses")

    if _captured:
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        saved = 0
        for item in _captured:
            try:
                save_fixture(
                    url=item["url"],
                    status_code=item["status_code"],
                    text=item["text"],
                    json_data=item.get("json_data"),
                )
                saved += 1
            except Exception as e:
                print(f"  Save error: {e}")
        print(f"Saved {saved} fixtures to {FIXTURE_DIR}")

        from core.tester.mock.fixtures import list_fixtures

        fixtures = list_fixtures()
        print(f"\nTotal fixtures: {len(fixtures)}")
        for f in fixtures:
            print(f"  {f['file']}: {f['url'][:80]} ({f['text_length']} chars)")

    await close_db()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
