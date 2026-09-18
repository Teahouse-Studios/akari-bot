from core.constants.default import wiki_allowlist_url_default
from core.config.decorator import on_module_config


@on_module_config("wiki")
class WikiConfig:
    wiki_allowlist_url: str = wiki_allowlist_url_default
