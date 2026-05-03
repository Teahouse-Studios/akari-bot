from . import wiki
from core.constants.default import wiki_whitelist_url_default


@wiki.config()
class WikiConfig:
    wiki_whitelist_url: str = wiki_whitelist_url_default
