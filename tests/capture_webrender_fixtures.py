"""WebRender 语料捕获工具。

WebRender 依赖外部无头浏览器服务，测试环境通常不具备。此脚本以普通 HTTP 抓取
相同 URL 的响应，作为 `web_render.source()` 的替身语料落盘，使相关模块的解析与
格式化逻辑可在无浏览器环境下被测试覆盖。

对于必须由浏览器执行脚本才能渲染出内容的页面，抓取结果与真实渲染结果并不等价；
此时应改为手工编写最小语料，只保留被解析逻辑依赖的结构。

使用方式：
    python tests/capture_webrender_fixtures.py
"""

import asyncio
import sys
from urllib.parse import quote

sys.path.insert(0, ".")

from core.tester.mock.webrender import save_webrender_fixture, FIXTURE_DIR
from core.utils.http import get_url

# 需要录制的 URL 与用途说明。
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
