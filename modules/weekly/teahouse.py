from .rss_utils import fetch_latest_entry


async def get_rss():
    """
    Get RSS feed from lakeus.xyz
    """
    return await fetch_latest_entry(
        "https://lakeus.xyz/api.php?action=featuredfeed&feed=teahouse-weekly&feedformat=atom",
        "https://lakeus.xyz",
    )
