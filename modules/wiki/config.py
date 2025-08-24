from . import wiki


@wiki.config()
class WikiConfig:
    wiki_whitelist_url: str = "example.com"
