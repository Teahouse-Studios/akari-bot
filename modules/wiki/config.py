from . import wiki

@wiki.config()
class WikiConfig:
    """
    Wiki module configuration items.
    """

    wiki_whitelist_url: str = "example.com"
