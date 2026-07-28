"""构造无法录制的语料。

minecraft.net 对非浏览器请求返回拦截页，其内容只能由 WebRender 真实渲染取得，
录制工具无法覆盖。此处按解析逻辑实际依赖的结构手工构造最小语料，使 minecraft_news
与 mcv_rss 的解析、去重、推送分支得以在测试中执行；被跳过的仅是渲染本身。

语料内容为虚构数据，不代表线上真实内容。

使用方式：
    python tests/build_synthetic_fixtures.py
"""

import json
import sys

sys.path.insert(0, ".")

from core.tester.mock.webrender import save_webrender_fixture

MINECRAFT_NEWS_URL = (
    "https://www.minecraft.net/content/minecraftnet/language-masters/en-us/"
    "jcr:content/root/container/image_grid_a_copy_64.articles.page-1.json"
)

# minecraft_news 逐条读取 default_tile.title / sub_header 与 article_url、image.imageURL。
MINECRAFT_NEWS_PAYLOAD = {
    "article_grid": [
        {
            "default_tile": {
                "title": "Test Article Alpha",
                "sub_header": "A synthetic entry used by the scheduled task test.",
                "image": {"imageURL": "/content/test-alpha.png"},
            },
            "article_url": "/en-us/article/test-alpha",
        },
        {
            "default_tile": {
                "title": "Test Article Beta",
                "sub_header": "A second synthetic entry to cover multi-item handling.",
                "image": {"imageURL": "/content/test-beta.png"},
            },
            "article_url": "/en-us/article/test-beta",
        },
    ]
}

# mcv_rss 的 get_article 只从页面中取第一个 h1 作为标题，并以 "404" 判定页面不存在。
MCV_ARTICLE_TEMPLATE = (
    "<!DOCTYPE html><html><head><title>{title}</title></head>"
    "<body><h1>{title}</h1><p>Synthetic changelog body.</p></body></html>"
)

# minecraft_news 取到图片链接后会以 get_raw 拉取图片内容，语料按 URL 命中即可。
NEWS_IMAGE_URLS = [
    "https://www.minecraft.net/content/test-alpha.png",
    "https://www.minecraft.net/content/test-beta.png",
]

# 需要预置变更日志语料的版本号。线上版本推进后需同步更新，
# 缺失时 mcv_rss 只是取不到文章标题，不影响版本推送本身的断言。
MCV_VERSIONS = ("26.2", "26.3-snapshot-6")


# 稳定失败的外部端点。录制工具只保存成功响应，这些请求在测试中会回落到真实网络，
# 带着重试与超时耗掉数十秒，且结果随对方服务状态漂移。此处以其真实状态码固定下来，
# 使模块走到与线上一致的错误分支，同时把耗时降为零。
NEGATIVE_RESPONSES = [
    # 该推文不存在，接口稳定返回 404，模块据此提示「未找到推文」。
    ("https://react-tweet.vercel.app/api/tweet/1", 404, "Not Found"),
    # 皮肤渲染服务源站长期不可用，Cloudflare 返回 521。
    ("https://crafatar.com/renders/body/069a79f444e94726a5befca90e38aaf5?overlay", 521, ""),
    # 基岩版查询接口无响应，以 5xx 复现其超时后的对外表现。
    ("http://motd.wd-api.com/v1/bedrock?host=mc.hypixel.net&port=19132", 502, ""),
]


def build():
    saved = []

    from core.tester.mock.fixtures import save_fixture

    for url, status, text in NEGATIVE_RESPONSES:
        saved.append(save_fixture(url=url, status_code=status, text=text, method="GET"))

    saved.append(save_webrender_fixture(MINECRAFT_NEWS_URL, json.dumps(MINECRAFT_NEWS_PAYLOAD, ensure_ascii=False)))

    for url in NEWS_IMAGE_URLS:
        saved.append(save_webrender_fixture(url, "synthetic-image-bytes"))

    # 变更日志的 URL 由模块自身推导，此处直接复用其实现，避免规则不一致。
    from modules.mcv_rss import get_changelog_url

    for version in MCV_VERSIONS:
        link = get_changelog_url(version)
        if not link:
            print(f"  skipped {version}: 无法推导变更日志地址")
            continue
        saved.append(save_webrender_fixture(link, MCV_ARTICLE_TEMPLATE.format(title=f"Minecraft {version}")))

    for path in saved:
        print(f"  built {path.name}")
    print(f"\nBuilt {len(saved)} synthetic fixtures ({len(NEGATIVE_RESPONSES)} HTTP, rest WebRender).")


if __name__ == "__main__":
    build()
