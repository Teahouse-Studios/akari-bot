from core.constants.default import wiki_whitelist_url_default
from . import wiki


@wiki.config()
class WikiConfig:
    wiki_whitelist_url: str = wiki_whitelist_url_default
