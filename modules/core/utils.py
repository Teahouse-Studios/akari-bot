import platform
import time

import orjson
import psutil
from akari_bot_i18n.i18n import build_locale_snapshot
from cpuinfo import get_cpu_info

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, Plain, FormattedTime, I18NContext, Url
from core.component import module
from core.config.base import CoreConfig
from core.constants import all_locales_path, cache_path, lang_list, weblate_lang_codes
from core.database.models import SenderUnionBind, SenderUnionInfo
from core.i18n import get_available_locales, Locale
from core.utils.bash import run_sys_command
from core.utils.http import get_url

WEBLATE_LANGUAGES_API = "https://hosted.weblate.org/api/projects/akaribot/languages/"
TRANSLATION_PROGRESS_THRESHOLD = 95.0

# Weblate 语言列表的缓存文件。机器人每晚自动清空 cache 目录时一并清理，次日首次调用时重新拉取。
WEBLATE_LANGUAGES_CACHE = cache_path / "weblate_languages.json"

ver = module("version", base=True, doc=True)


def get_version_display() -> str | None:
    if not Bot.Info.version:
        return None
    version = str(Bot.Info.version)
    return version[4:11] if version.startswith("git:") else version


@ver.command("{{I18N:core.help.version}}")
async def _(msg: Bot.MessageSession):
    if version_display := get_version_display():
        send_msgs = MessageChain.assign(I18NContext("core.message.version", version=version_display, disable_joke=True))
        if str(Bot.Info.version).startswith("git:"):
            if CoreConfig.enable_commit_url:
                returncode, repo_url, _ = await run_sys_command(["git", "config", "--get", "remote.origin.url"])
                if returncode == 0:
                    repo_url = repo_url.strip().replace(".git", "")
                    commit_url = f"{repo_url}/commit/{version_display}"
                    send_msgs.append(Url(commit_url, trusted=True))
        else:
            if CoreConfig.enable_commit_url:
                version_tag = "nightly" if version_display.startswith("nightly") else version_display
                returncode, repo_url, _ = await run_sys_command(["git", "config", "--get", "remote.origin.url"])
                if returncode == 0:
                    repo_url = repo_url.strip().replace(".git", "")
                    commit_url = f"{repo_url}/releases/tag/{version_tag}"
                    send_msgs.append(Url(commit_url, trusted=True))
        await msg.finish(send_msgs)
    else:
        await msg.finish(I18NContext("core.message.version.unknown"))


ping = module("ping", base=True, doc=True)

started_time = time.time()


@ping.command("{{I18N:core.help.ping}}")
async def _(msg: Bot.MessageSession):
    result = MessageChain.assign(Plain("Pong!"))

    td_seconds = time.time() - started_time
    timediff = f"{int(td_seconds // 3600):02d}:{int((td_seconds % 3600) // 60):02d}:{int(td_seconds % 60):02d}"
    cpu_percent = psutil.cpu_percent()
    ram_percent = psutil.virtual_memory().percent
    if msg.check_super_user():
        boot_start = str(FormattedTime(psutil.boot_time(), iso=True))
        web_render_status = str(Bot.Info.web_render_status)
        ram = int(psutil.virtual_memory().total / (1024 * 1024))
        swap = int(psutil.swap_memory().total / (1024 * 1024))
        swap_percent = psutil.swap_memory().percent
        disk = int(psutil.disk_usage("/").used / (1024 * 1024 * 1024))
        disk_total = int(psutil.disk_usage("/").total / (1024 * 1024 * 1024))
        result.append(
            I18NContext(
                "core.message.ping.detail",
                system_boot_time=boot_start,
                bot_running_time=timediff,
                python_version=platform.python_version(),
                web_render_status=web_render_status,
                cpu_brand=get_cpu_info()["brand_raw"],
                cpu_percent=cpu_percent,
                ram=ram,
                ram_percent=ram_percent,
                swap=swap,
                swap_percent=swap_percent,
                disk_space=disk,
                disk_space_total=disk_total,
                client_name=msg.session_info.client_name,
                command_parsed=Bot.Info.command_parsed,
                parsed=Bot.Info.message_parsed,
                disable_joke=True,
            )
        )
    else:
        disk_percent = psutil.disk_usage("/").percent
        result.append(
            I18NContext(
                "core.message.ping.simple",
                bot_running_time=timediff,
                cpu_percent=cpu_percent,
                ram_percent=ram_percent,
                disk_percent=disk_percent,
                disable_joke=True,
            )
        )
    await msg.finish(result)


admin = module(
    "admin",
    base=True,
    required_admin=True,
    alias={"ban": "admin ban", "unban": "admin unban", "ban list": "admin ban list"},
    desc="{I18N:core.help.admin.desc}",
    doc=True,
)


async def _display_union_list(msg: Bot.MessageSession, union_ids: list[str]) -> list[str]:
    """
    将权限列表中的 union ID 展开为其下绑定的平台账号 ID 用于展示，一行对应一个 union。
    """
    delimiter = str(I18NContext("message.delimiter"))
    lines = []
    for union_id in union_ids:
        bound_ids = await SenderUnionBind.list_ids(union_id)
        lines.append(delimiter.join(bound_ids) if bound_ids else union_id)
    return lines


async def _resolve_union_id(user: str, create: bool = True) -> str:
    """
    将平台账号 ID 解析为写入权限列表的 union ID，未绑定任何 union 时退回原 ID。
    """
    sender_union_info = await SenderUnionInfo.resolve_union(user, create)
    return sender_union_info.union_id if sender_union_info else user


@admin.command(
    "add <user> {{I18N:core.help.admin.add}}",
    "remove <user> {{I18N:core.help.admin.remove}}",
    "list {{I18N:core.help.admin.list}}",
)
async def _(msg: Bot.MessageSession):
    if "list" in msg.parsed_msg:
        if msg.session_info.custom_admins:
            await msg.finish(
                [I18NContext("core.message.admin.list")]
                + await _display_union_list(msg, msg.session_info.custom_admins)
            )
        else:
            await msg.finish(I18NContext("core.message.admin.list.none"))
    user = msg.parsed_msg["<user>"]
    if not user.startswith(f"{msg.session_info.sender_from}|"):
        await msg.finish(
            I18NContext(
                "core.message.admin.invalid",
                sender=msg.session_info.sender_from,
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}whoami"),
            )
        )
    if "add" in msg.parsed_msg:
        union_id = await _resolve_union_id(user)
        if union_id in msg.session_info.custom_admins:
            await msg.finish(I18NContext("core.message.admin.add.already"))
        if await msg.session_info.target_union_info.config_custom_admin(union_id):
            await msg.finish(I18NContext("core.message.admin.add.success", sender=user))
    if "remove" in msg.parsed_msg:
        union_id = await _resolve_union_id(user, create=False)
        if union_id == msg.session_info.sender_union_id:
            if not await msg.wait_confirm(I18NContext("core.message.admin.remove.confirm")):
                await msg.finish()
        if await msg.session_info.target_union_info.config_custom_admin(union_id, enable=False):
            await msg.finish(I18NContext("core.message.admin.remove.success", sender=user))


@admin.command(
    "ban <user> {{I18N:core.help.admin.ban}}",
    "unban <user> {{I18N:core.help.admin.unban}}",
    "ban list {{I18N:core.help.admin.ban.list}}",
)
async def _(msg: Bot.MessageSession):
    if "list" in msg.parsed_msg:
        if msg.session_info.banned_users:
            await msg.finish(
                [I18NContext("core.message.admin.ban.list")]
                + await _display_union_list(msg, msg.session_info.banned_users)
            )
        else:
            await msg.finish(I18NContext("core.message.admin.ban.list.none"))
    user = msg.parsed_msg["<user>"]
    if not user.startswith(f"{msg.session_info.sender_from}|"):
        await msg.finish(
            I18NContext(
                "core.message.admin.invalid",
                sender=msg.session_info.sender_from,
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}whoami"),
            )
        )
    if "ban" in msg.parsed_msg:
        union_id = await _resolve_union_id(user)
        if union_id == msg.session_info.sender_union_id:
            await msg.finish(I18NContext("core.message.admin.ban.self"))
        if union_id in msg.session_info.banned_users:
            await msg.finish(I18NContext("core.message.admin.ban.already"))
        await msg.session_info.target_union_info.config_banned_user(union_id)
        await msg.finish(I18NContext("core.message.admin.ban.success", sender=user))
    if "unban" in msg.parsed_msg:
        union_id = await _resolve_union_id(user, create=False)
        if await msg.session_info.target_union_info.config_banned_user(union_id, enable=False):
            await msg.finish(I18NContext("core.message.admin.unban.success", sender=user))


locale = module("locale", base=True, desc="{I18N:core.help.locale.desc}", alias="lang", doc=True)


def build_locale_list(msg: Bot.MessageSession) -> list:
    """构造逐行显示的可用语言列表。"""
    locales = [(lang, Locale(lang).t("language")) for lang in get_available_locales()]
    if not msg.session_info.support_action_text:
        return [I18NContext("core.message.locale.langlist", langlist="\n".join(name for _, name in locales))]

    prefix = msg.session_info.prefixes[0]
    parts = []
    for index, (lang, name) in enumerate(locales):
        parts.append(ActionText(f"{prefix}locale {lang}", show=name))
        parts.append(Plain("\n" if index + 1 < len(locales) else " ", disable_joke=True))
    return [I18NContext("core.message.locale.langlist", langlist=MessageChain.assign(parts))]


def build_locale_overview(msg: Bot.MessageSession, locale_url: str | None) -> list:
    """构造语言命令的概览消息。"""
    res = [
        I18NContext("core.message.locale.prompt", lang="{I18N:language}"),
        I18NContext(
            "core.message.locale.set.prompt",
            prefix=msg.session_info.prefixes[0],
            cmd=ActionText(f"{msg.session_info.prefixes[0]}locale "),
        ),
        *build_locale_list(msg),
    ]
    if locale_url:
        res.append(
            I18NContext(
                "core.message.locale.contribute",
                url=MessageChain.assign(Url(locale_url, trusted=True)),
            )
        )
    return res


async def get_weblate_languages() -> list | None:
    """获取 Weblate 的语言列表，结果缓存到 cache 目录以复用。

    机器人每晚会自动清空 cache 目录，因此缓存会在次日首次调用时重新拉取。
    """
    if WEBLATE_LANGUAGES_CACHE.is_file():
        try:
            languages = orjson.loads(WEBLATE_LANGUAGES_CACHE.read_bytes())
        except Exception:
            languages = None
        if isinstance(languages, list):
            return languages
        # 缓存损坏时移除，避免后续反复命中坏文件。
        try:
            WEBLATE_LANGUAGES_CACHE.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        languages = await get_url(WEBLATE_LANGUAGES_API, fmt="json", timeout=5, logging_err_resp=False)
    except Exception:
        return None
    if not isinstance(languages, list):
        return None
    try:
        WEBLATE_LANGUAGES_CACHE.parent.mkdir(parents=True, exist_ok=True)
        WEBLATE_LANGUAGES_CACHE.write_bytes(orjson.dumps(languages))
    except OSError:
        pass
    return languages


async def build_translation_notice(lang: str):
    """当目标语言在 Weblate 的翻译进度低于阈值时，构造邀请参与翻译的消息。"""
    weblate_code = weblate_lang_codes.get(lang)
    if not weblate_code:
        return None
    languages = await get_weblate_languages()
    if not languages:
        return None
    entry = next((item for item in languages if isinstance(item, dict) and item.get("code") == weblate_code), None)
    if not entry:
        return None
    progress = entry.get("translated_percent")
    if not isinstance(progress, (int, float)) or progress >= TRANSLATION_PROGRESS_THRESHOLD:
        return None
    return [
        I18NContext(
            "core.message.locale.translation_progress", name=Locale(lang).t("language"), percent=f"{progress:g}"
        ),
        Url(entry.get("url") or CoreConfig.locale_url, trusted=True),
    ]


@locale.command()
async def _(msg: Bot.MessageSession):
    await msg.send_message(build_locale_overview(msg, CoreConfig.locale_url))
    await msg.finish(await build_translation_notice(msg.session_info.locale.locale))


@locale.command("[<lang>] {{I18N:core.help.locale.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, lang: str):
    if lang in get_available_locales():
        await msg.session_info.target_union_info.edit_attr("locale", lang)
        await msg.send_message(Locale(lang).t("message.success"))
        await msg.finish(await build_translation_notice(lang))
    else:
        await msg.finish([I18NContext("core.message.locale.set.invalid"), *build_locale_list(msg)])


@locale.command("reload", required_superuser=True)
async def _(msg: Bot.MessageSession):
    err = build_locale_snapshot(list(lang_list.keys()), all_locales_path, "akari-bot")
    if len(err) == 0:
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish([I18NContext("core.message.locale.reload.failed"), Plain("\n".join(err), disable_joke=True)])


whoami = module("whoami", base=True, doc=True)


@whoami.command("{{I18N:core.help.whoami}}")
async def _(msg: Bot.MessageSession):
    sender_union_info = msg.session_info.sender_union_info
    target_union_info = msg.session_info.target_union_info

    msgchain = [
        I18NContext("core.message.whoami.sender", id=msg.session_info.sender_id, disable_joke=True),
        I18NContext("core.message.whoami.target", id=msg.session_info.target_id, disable_joke=True),
    ]

    if sender_union_info and msg.session_info.sender_id != sender_union_info.union_id:
        msgchain.append(
            I18NContext("core.message.whoami.sender.union", id=sender_union_info.union_id, disable_joke=True)
        )
    if msg.session_info.target_id != target_union_info.union_id:
        msgchain.append(
            I18NContext("core.message.whoami.target.union", id=target_union_info.union_id, disable_joke=True)
        )
    if await msg.check_native_permission():
        msgchain.append(I18NContext("core.message.whoami.admin"))
    elif await msg.check_permission():
        msgchain.append(I18NContext("core.message.whoami.botadmin"))
    if msg.check_super_user():
        msgchain.append(I18NContext("core.message.whoami.superuser"))

    await msg.finish(msgchain)


mute = module("mute", base=True, doc=True, required_admin=True)


@mute.command("{{I18N:core.help.mute}}")
async def _(msg: Bot.MessageSession):
    state = await msg.session_info.target_union_info.switch_mute()
    if state:
        await msg.finish(I18NContext("core.message.mute.enable"))
    else:
        await msg.finish(I18NContext("core.message.mute.disable"))


leave = module(
    "leave",
    alias="dismiss",
    base=True,
    doc=True,
    required_admin=True,
    available_for=["QQ|Group"],
)


@leave.command("{{I18N:core.help.leave}}")
async def _(msg: Bot.MessageSession):
    if await msg.wait_confirm(I18NContext("core.message.leave.confirm")):
        await msg.send_message(I18NContext("core.message.leave.success"))
        await msg.call_onebot_api("set_group_leave", group_id=int(msg.session_info.get_common_target_id()))
    else:
        await msg.finish()
