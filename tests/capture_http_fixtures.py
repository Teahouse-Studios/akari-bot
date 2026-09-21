"""HTTP Fixture 捕获工具 - 运行集成测试并将真实响应录制到本地文件。"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.mock.fixtures import save_fixture, list_fixtures, FIXTURE_DIR
from core.tester.mock.http import digest_request_body

INTEGRATION_DIR = Path(__file__).parent / "integration"

# 以 (URL, method, 请求体摘要) 为键去重：同一 URL 上请求体不同的调用需各自成为一份 fixture。
_captured: dict[tuple, dict] = {}
_failures: list[tuple[str, str]] = []


def _normalize(result):
    if isinstance(result, bytes):
        # fmt="read"/"content" 的下载类请求返回二进制，无法直接写入 JSON。
        return "", None, result
    if isinstance(result, str):
        return result, None, b""
    try:
        return json.dumps(result, ensure_ascii=False), result, b""
    except (TypeError, ValueError):
        return str(result), None, b""


async def _run_test_files(names: list[str]):
    from core.tester.tester import Tester

    for path in sorted(INTEGRATION_DIR.glob("test_*.py")):
        if names and not any(n in path.stem for n in names):
            continue
        module_name = f"tests.integration.{path.stem}"
        print(f"\n>> {module_name}")
        try:
            mod = __import__(module_name, fromlist=["*"])
        except Exception as e:
            print(f"   module load error: {type(e).__name__}: {e}")
            continue

        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if callable(attr) and getattr(attr, "_func_case", False):
                print(f"   running {attr_name}")
                try:
                    await attr(Tester(attr_name))
                except Exception as e:
                    print(f"   {attr_name} raised {type(e).__name__}: {e}")


async def main():
    names = sys.argv[1:]

    print("=" * 60)
    print("HTTP Fixture Capture Tool")
    print("=" * 60)

    await init_db()
    # 录制阶段必须关闭 fixture 回放，否则会把上一轮的 mock 结果再录一遍。
    await load_modules(show_logs=False, monkey_patches={"Random": Random()}, load_fixtures=False)

    import core.utils.http as http_module

    original_request_url = http_module.request_url

    async def capturing_request_url(url, method="GET", **kwargs):
        try:
            result = await original_request_url(url, method=method, **kwargs)
        except Exception as e:
            _failures.append((f"[{method}] {url}", f"{type(e).__name__}: {e}"))
            print(f"  ERROR    [{method}] {url[:80]} -> {type(e).__name__}")
            raise

        body = kwargs.get("data")
        text, json_data, content = _normalize(result)
        _captured[(url, method.upper(), digest_request_body(body))] = {
            "url": url,
            "method": method,
            "status_code": kwargs.get("status_code") or 200,
            "text": text,
            "json_data": json_data,
            "content": content,
            "request_body": body,
        }
        size = len(content) if content else len(text)
        print(f"  CAPTURED [{method}] {url[:80]} ({size} bytes)")
        return result

    http_module.request_url = capturing_request_url
    try:
        print("\n--- Running integration tests ---")
        await _run_test_files(names)
    finally:
        http_module.request_url = original_request_url

    print(f"\n{'=' * 60}")
    print(f"Captured {len(_captured)} unique responses, {len(_failures)} request failures")

    saved = 0
    if _captured:
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        for item in _captured.values():
            try:
                save_fixture(
                    url=item["url"],
                    status_code=item["status_code"],
                    text=item["text"],
                    content=item["content"],
                    json_data=item["json_data"],
                    method=item["method"],
                    request_body=item["request_body"],
                )
                saved += 1
            except Exception as e:
                print(f"  save error for {item['url'][:60]}: {type(e).__name__}: {e}")
        print(f"Saved {saved} fixtures to {FIXTURE_DIR}")

    if _failures:
        print("\nRequests that failed (not recorded):")
        for target, reason in _failures:
            print(f"  {target[:90]} -> {reason[:60]}")

    print(f"\nTotal fixtures on disk: {len(list_fixtures())}")
    await close_db()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
