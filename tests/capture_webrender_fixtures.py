"""WebRender 语料捕获工具。"""

import asyncio
import sys
from urllib.parse import quote

sys.path.insert(0, ".")

from core.tester.mock.webrender import save_webrender_fixture, FIXTURE_DIR
from core.utils.http import get_url

TARGETS = [
    ("https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/", "arcaea download 版本信息"),
    (f"https://search.mcmod.cn/s?key={quote('创建')}", "mcmod 搜索结果页"),
]


async def main():
    print("=" * 60)
    print("WebRender Fixture Capture Tool")
    print("=" * 60)

    saved = 0
    for url, note in TARGETS:
        try:
            text = await get_url(url, timeout=30, attempt=2, logging_err_resp=False)
        except Exception as e:
            print(f"  FAIL     {note}: {type(e).__name__}: {str(e)[:60]}")
            continue
        path = save_webrender_fixture(url, text)
        saved += 1
        print(f"  CAPTURED {note}: {len(text)} chars -> {path.name}")

    print(f"\nSaved {saved}/{len(TARGETS)} fixtures to {FIXTURE_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
