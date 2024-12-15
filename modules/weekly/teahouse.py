import feedparser

from core.utils.html2text import html2text
from core.utils.http import get_url


async def get_rss():
    """
    Get RSS feed from lakeus.xyz
    """
    url = await get_url(
        "https://lakeus.xyz/api.php?action=featuredfeed&feed=teahouse-weekly&feedformat=atom",
        status_code=200,
        fmt="text",
    )
    feed = feedparser.parse(url)["entries"][-1]
    title = feed["title"]
    summary = html2text(feed["summary"], baseurl="https://lakeus.xyz")
    return title + "\n" + summary
