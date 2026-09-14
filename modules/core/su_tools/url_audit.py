from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Image
from core.component import module
from core.utils.image_table import ImageTable, image_table_render
from core.utils.url_audit import GlobalURLAllowlist, GlobalURLBlocklist, URLRule, URLRuleError

url = module(
    "url-audit",
    required_superuser=True,
    base=True,
)


def _url_rule_error(msg: Bot.MessageSession, list_name: str, error: URLRuleError):
    reason = msg.session_info.locale.t(f"core.message.url-audit.{list_name}.error.reason.{error.reason}")
    return I18NContext(f"core.message.url-audit.{list_name}.error.invalid", reason=reason)


def _url_rule_details(msg: Bot.MessageSession, list_name: str, rules) -> str:
    return "\n".join(
        f"[{msg.session_info.locale.t(f'core.message.url-audit.source.{list_name}.{rule.source}')}] {rule.serialized}"
        for rule in rules
    )


async def _finish_url_rule_list(msg: Bot.MessageSession, list_name: str, rules: tuple[URLRule, ...]) -> None:
    locale = msg.session_info.locale
    table = ImageTable(
        [
            [
                locale.t(f"core.message.url-audit.{list_name}.source.{rule.source}"),
                locale.t("core.message.url-audit.list.table.type.regex")
                if rule.is_regex
                else locale.t("core.message.url-audit.list.table.type.exact"),
                rule.value,
            ]
            for rule in rules
        ],
        [
            locale.t("core.message.url-audit.list.table.header.source"),
            locale.t("core.message.url-audit.list.table.header.type"),
            locale.t("core.message.url-audit.list.table.header.rule"),
        ],
        disable_joke=True,
    )
    imgs = await image_table_render(table)
    if not imgs:
        await msg.finish()
    await msg.finish([I18NContext(f"core.message.url-audit.{list_name}.list.title")] + [Image(img) for img in imgs])


@url.command(
    [
        "allowlist add <url> {{I18N:core.help.url-audit.allowlist.add}}",
        "allowlist add-regex <url> {{I18N:core.help.url-audit.allowlist.add_regex}}",
    ]
)
async def _(msg: Bot.MessageSession, url: str):
    is_regex = bool(msg.parsed_msg.get("add-regex", False))
    try:
        added = GlobalURLAllowlist.add_user_rule(url, is_regex=is_regex)
    except URLRuleError as exc:
        await msg.finish(_url_rule_error(msg, "allowlist", exc))
    await msg.finish(
        I18NContext(
            "core.message.url-audit.allowlist.add.success" if added else "core.message.url-audit.allowlist.add.exists",
            rule=(f"regex:{url.strip()}" if is_regex else url),
        )
    )


@url.command(
    [
        "allowlist remove <url> {{I18N:core.help.url-audit.allowlist.remove}}",
        "allowlist remove-regex <url> {{I18N:core.help.url-audit.allowlist.remove_regex}}",
    ]
)
async def _(msg: Bot.MessageSession, url: str):
    is_regex = bool(msg.parsed_msg.get("remove-regex", False))
    try:
        removed = GlobalURLAllowlist.remove_user_rule(url, is_regex=is_regex)
    except URLRuleError as exc:
        await msg.finish(_url_rule_error(msg, "allowlist", exc))
    await msg.finish(
        I18NContext(
            "core.message.url-audit.allowlist.remove.success"
            if removed
            else "core.message.url-audit.allowlist.remove.missing",
            rule=(f"regex:{url.strip()}" if is_regex else url),
        )
    )


@url.command("allowlist query <url> {{I18N:core.help.url-audit.allowlist.query}}")
async def _(msg: Bot.MessageSession, url: str):
    matches = GlobalURLAllowlist.matching_rules(url)
    if not matches:
        await msg.finish(I18NContext("core.message.url-audit.allowlist.query.denied", url=url))
    details = _url_rule_details(msg, "allowlist", matches)
    await msg.finish(I18NContext("core.message.url-audit.allowlist.query.allowed", url=url, rules=details))


@url.command("allowlist list {{I18N:core.help.url-audit.allowlist.list}}")
async def _(msg: Bot.MessageSession):
    rules = GlobalURLAllowlist.rules()
    if not rules:
        await msg.finish(I18NContext("core.message.url-audit.allowlist.list.empty"))
    await _finish_url_rule_list(msg, "allowlist", rules)


@url.command(
    [
        "blocklist add <url> {{I18N:core.help.url-audit.blocklist.add}}",
        "blocklist add-regex <url> {{I18N:core.help.url-audit.blocklist.add_regex}}",
    ]
)
async def _(msg: Bot.MessageSession, url: str):
    is_regex = bool(msg.parsed_msg.get("add-regex", False))
    try:
        added = GlobalURLBlocklist.add_user_rule(url, is_regex=is_regex)
    except URLRuleError as exc:
        await msg.finish(_url_rule_error(msg, "blocklist", exc))
    await msg.finish(
        I18NContext(
            "core.message.url-audit.blocklist.add.success" if added else "core.message.url-audit.blocklist.add.exists",
            rule=(f"regex:{url.strip()}" if is_regex else url),
        )
    )


@url.command(
    [
        "blocklist remove <url> {{I18N:core.help.url-audit.blocklist.remove}}",
        "blocklist remove-regex <url> {{I18N:core.help.url-audit.blocklist.remove_regex}}",
    ]
)
async def _(msg: Bot.MessageSession, url: str):
    is_regex = bool(msg.parsed_msg.get("remove-regex", False))
    try:
        removed = GlobalURLBlocklist.remove_user_rule(url, is_regex=is_regex)
    except URLRuleError as exc:
        await msg.finish(_url_rule_error(msg, "blocklist", exc))
    await msg.finish(
        I18NContext(
            "core.message.url-audit.blocklist.remove.success"
            if removed
            else "core.message.url-audit.blocklist.remove.missing",
            rule=(f"regex:{url.strip()}" if is_regex else url),
        )
    )


@url.command("blocklist query <url> {{I18N:core.help.url-audit.blocklist.query}}")
async def _(msg: Bot.MessageSession, url: str):
    matches = GlobalURLBlocklist.matching_rules(url)
    if not matches:
        await msg.finish(I18NContext("core.message.url-audit.blocklist.query.allowed", url=url))
    details = _url_rule_details(msg, "blocklist", matches)
    await msg.finish(I18NContext("core.message.url-audit.blocklist.query.blocked", url=url, rules=details))


@url.command("blocklist list {{I18N:core.help.url-audit.blocklist.list}}")
async def _(msg: Bot.MessageSession):
    rules = GlobalURLBlocklist.rules()
    if not rules:
        await msg.finish(I18NContext("core.message.url-audit.blocklist.list.empty"))
    await _finish_url_rule_list(msg, "blocklist", rules)
