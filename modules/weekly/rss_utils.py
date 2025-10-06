import feedparser

from core.logger import Logger
from core.utils.html2text import html2text
from core.utils.http import get_url


class RSSFeedError(RuntimeError):
    """Raised when the RSS feed cannot be parsed or contains no entries."""


async def fetch_latest_entry(feed_url: str, base_url: str, *, entry_index: int = -1) -> str:
    """Fetch the latest entry from an RSS feed.

    Args:
        feed_url: The URL of the RSS/Atom feed.
        base_url: The base URL used for resolving relative paths in summaries.
        entry_index: The index of the entry to fetch. Defaults to the latest (-1).

    Returns:
        A string containing the formatted title and summary.

    Raises:
        RSSFeedError: If the feed cannot be fetched or contains no entries.
    """

    text = await get_url(feed_url, status_code=200, fmt="text")
    parsed = feedparser.parse(text)
    if getattr(parsed, "bozo", 0):
        Logger.warning(
            f"RSS feed at {feed_url} raised parse error: {getattr(parsed, 'bozo_exception', 'unknown error')}"
        )
        raise RSSFeedError("Failed to parse RSS feed content")
    entries = parsed.get("entries")

    if not entries:
        Logger.warning(f"RSS feed at {feed_url} returned no entries")
        raise RSSFeedError("The RSS feed contains no entries")

    try:
        feed = entries[entry_index]
    except IndexError as exc:
        Logger.error(
            f"Invalid entry index {entry_index} for feed {feed_url} (available: {len(entries)})"
        )
        raise RSSFeedError("The requested feed entry does not exist") from exc

    title = feed.get("title")
    summary = feed.get("summary")

    if not title or not summary:
        Logger.error(f"Feed entry missing required fields for feed {feed_url}")
        raise RSSFeedError("Feed entry missing required fields")

    rendered_summary = html2text(summary, baseurl=base_url)
    return f"{title}\n{rendered_summary}"
