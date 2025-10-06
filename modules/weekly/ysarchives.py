from .rss_utils import fetch_latest_entry


async def get_rss():
    """
    Get RSS feed from YsArchives
    """
    return await fetch_latest_entry(
        "https://youshou.wiki/api.php?action=featuredfeed&feed=ysarchives-biweekly&feedformat=atom",
        "https://youshou.wiki",
    )
