from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.utils.url_policy import GlobalURLAllowlist, GlobalURLBlocklist, URLRuleError
from .utils.wikilib import BlockedWikiError, WikiLib

aud = module(
    "wiki-audit",
    required_superuser=True,
    alias=["wiki_audit", "wau"],
    desc="{I18N:wiki.help.wiki_audit.desc}",
    doc=True,
)


def _url_rule_error(msg: Bot.MessageSession, list_name: str, error: URLRuleError) -> I18NContext:
    reason = msg.session_info.locale.t(f"core.message.url_{list_name}.error.reason.{error.reason}")
    return I18NContext(f"core.message.url_{list_name}.error.invalid", reason=reason)


def _url_rule_details(msg: Bot.MessageSession, rules) -> str:
    return "\n".join(
        f"[{msg.session_info.locale.t(f'core.message.url_allowlist.source.{rule.source}')}] {rule.serialized}"
        for rule in rules
    )


async def _resolve_wiki_api(msg: Bot.MessageSession, wikiurl: str, *, error_action: str) -> str:
    """将 Wiki 页面、站点或 API 地址解析为规范 API URL。"""
    try:
        check = await WikiLib(wikiurl).check_wiki_available()
    except BlockedWikiError as exc:
        await msg.finish(I18NContext("wiki.message.invalid.blocked", name=exc.url))

    if not check.available:
        prompts = [I18NContext(f"wiki.message.error.{error_action}")]
        if check.message:
            prompts.extend((I18NContext("wiki.message.error.info"), Plain(check.message)))
        await msg.finish(MessageChain.assign(prompts))
    return check.value.api


async def _resolve_cached_wiki_api(wikiurl: str) -> str:
    """移除规则时优先使用缓存，以兼容已不可访问的 Wiki。"""
    check = await WikiLib(wikiurl).check_wiki_info_from_database_cache()
    return check.value.api if check.available else wikiurl


@aud.command(
    [
        "trust <wikiurl> {{I18N:wiki.help.wiki_audit.trust}}",
        "block <wikiurl> {{I18N:wiki.help.wiki_audit.block}}",
    ]
)
async def _(msg: Bot.MessageSession, wikiurl: str):
    api_url = await _resolve_wiki_api(msg, wikiurl, error_action="add")
    is_block = bool(msg.parsed_msg.get("block", False))
    list_name = "blocklist" if is_block else "allowlist"
    rule_list = GlobalURLBlocklist if is_block else GlobalURLAllowlist

    try:
        added = rule_list.add_user_rule(api_url)
    except URLRuleError as exc:
        await msg.finish(_url_rule_error(msg, list_name, exc))

    await msg.finish(
        I18NContext(
            f"core.message.url_{list_name}.add.{'success' if added else 'exists'}",
            rule=api_url,
        )
    )


@aud.command(
    [
        "distrust <wikiurl> {{I18N:wiki.help.wiki_audit.distrust}}",
        "unblock <wikiurl> {{I18N:wiki.help.wiki_audit.unblock}}",
    ]
)
async def _(msg: Bot.MessageSession, wikiurl: str):
    api_url = await _resolve_cached_wiki_api(wikiurl)
    is_unblock = bool(msg.parsed_msg.get("unblock", False))
    list_name = "blocklist" if is_unblock else "allowlist"
    rule_list = GlobalURLBlocklist if is_unblock else GlobalURLAllowlist
    try:
        removed = rule_list.remove_user_rule(api_url)
    except URLRuleError as exc:
        await msg.finish(_url_rule_error(msg, list_name, exc))
    await msg.finish(
        I18NContext(
            f"core.message.url_{list_name}.remove.{'success' if removed else 'missing'}",
            rule=api_url,
        )
    )


@aud.command("query <wikiurl> {{I18N:wiki.help.wiki_audit.query}}")
async def _(msg: Bot.MessageSession, wikiurl: str):
    api_url = await _resolve_wiki_api(msg, wikiurl, error_action="query")
    matches = GlobalURLAllowlist.matching_rules(api_url)
    if not matches:
        await msg.finish(I18NContext("core.message.url_allowlist.query.denied", url=api_url))
    await msg.finish(
        I18NContext(
            "core.message.url_allowlist.query.allowed",
            url=api_url,
            rules=_url_rule_details(msg, matches),
        )
    )
