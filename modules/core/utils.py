import platform
from datetime import datetime

import psutil
from cpuinfo import get_cpu_info

from core.builtins import Bot, Plain, I18NContext, Url
from core.component import module
from core.config import Config
from core.constants import locale_url_default
from core.i18n import get_available_locales, Locale, load_locale_file
from core.utils.bash import run_sys_command
from core.utils.info import Info


ver = module("version", base=True, doc=True)


@ver.command("{{core.help.version}}")
async def _(msg: Bot.MessageSession):
    if Info.version:
        commit = Info.version[0:6]
        send_msgs = [I18NContext("core.message.version", disable_joke=True, commit=commit)]
        if Config("enable_commit_url", True):
            returncode, repo_url, _ = await run_sys_command(["git", "config", "--get", "remote.origin.url"])
            if returncode == 0:
                repo_url = repo_url.strip().replace(".git", "")
                commit_url = f"{repo_url}/commit/{commit}"
                send_msgs.append(Url(commit_url))
        await msg.finish(send_msgs)
    else:
        await msg.finish(I18NContext("core.message.version.unknown"))


ping = module("ping", base=True, doc=True)

started_time = datetime.now()


@ping.command("{{core.help.ping}}")
async def _(msg: Bot.MessageSession):
    result = [Plain("Pong!")]
    timediff = str(datetime.now() - started_time).split(".")[0]
    if msg.check_super_user():
        boot_start = msg.ts2strftime(psutil.boot_time())
        web_render_status = str(Info.web_render_status)
        cpu_usage = psutil.cpu_percent()
        ram = int(psutil.virtual_memory().total / (1024 * 1024))
        ram_percent = psutil.virtual_memory().percent
        swap = int(psutil.swap_memory().total / (1024 * 1024))
        swap_percent = psutil.swap_memory().percent
        disk = int(psutil.disk_usage("/").used / (1024 * 1024 * 1024))
        disk_total = int(psutil.disk_usage("/").total / (1024 * 1024 * 1024))
        result.append(I18NContext(
            "core.message.ping.detail",
            system_boot_time=boot_start,
            bot_running_time=timediff,
            python_version=platform.python_version(),
            web_render_status=web_render_status,
            cpu_brand=get_cpu_info()["brand_raw"],
            cpu_usage=cpu_usage,
            ram=ram,
            ram_percent=ram_percent,
            swap=swap,
            swap_percent=swap_percent,
            disk_space=disk,
            disk_space_total=disk_total,
            client_name=Info.client_name,
            command_parsed=Info.command_parsed,
        ))
    else:
        disk_percent = psutil.disk_usage("/").percent
        result.append(I18NContext(
            "core.message.ping.simple",
            bot_running_time=timediff,
            disk_percent=disk_percent,
        ))
    await msg.finish(result)


admin = module(
    "admin",
    base=True,
    required_admin=True,
    alias={"ban": "admin ban", "unban": "admin unban", "ban list": "admin ban list"},
    desc="{core.help.admin.desc}",
    doc=True,
    exclude_from=["TEST|Console"],
)


@admin.command(
    "add <user> {{core.help.admin.add}}",
    "remove <user> {{core.help.admin.remove}}",
    "list {{core.help.admin.list}}")
async def _(msg: Bot.MessageSession):
    if "list" in msg.parsed_msg:
        if msg.custom_admins:
            await msg.finish([I18NContext("core.message.admin.list"), Plain("\n".join(msg.custom_admins))])
        else:
            await msg.finish(I18NContext("core.message.admin.list.none"))
    user = msg.parsed_msg["<user>"]
    if not user.startswith(f"{msg.target.sender_from}|"):
        await msg.finish(I18NContext("core.message.admin.invalid", sender=msg.target.sender_from, prefix=msg.prefixes[0]))
    if "add" in msg.parsed_msg:
        if user and user not in msg.custom_admins:
            if await msg.target_info.config_custom_admin(user):
                await msg.finish(I18NContext("core.message.admin.add.success", user=user))
        else:
            await msg.finish(I18NContext("core.message.admin.already"))
    if "remove" in msg.parsed_msg:
        if user == msg.target.sender_id:
            confirm = await msg.wait_confirm(I18NContext("core.message.admin.remove.confirm"))
            if not confirm:
                await msg.finish()
        elif user and msg.target_info.config_custom_admin(user, enable=False):
            await msg.finish(I18NContext("core.message.admin.remove.success", user=user))


@admin.command(
    "ban <user> {{core.help.admin.ban}}",
    "unban <user> {{core.help.admin.unban}}",
    "ban list {{core.help.admin.ban.list}}",
)
async def _(msg: Bot.MessageSession):
    admin_ban_list = msg.target_data.get("ban", [])
    if "list" in msg.parsed_msg:
        if admin_ban_list:
            await msg.finish([I18NContext("core.message.admin.ban.list"), Plain("\n".join(admin_ban_list))])
        else:
            await msg.finish(I18NContext("core.message.admin.ban.list.none"))
    user = msg.parsed_msg["<user>"]
    if not user.startswith(f"{msg.target.sender_from}|"):
        await msg.finish(I18NContext("core.message.admin.invalid", sender=msg.target.sender_from, prefix=msg.prefixes[0]))
    if user == msg.target.sender_id:
        await msg.finish(I18NContext("core.message.admin.ban.self"))
    if "ban" in msg.parsed_msg:
        if user not in admin_ban_list:
            await msg.target_info.edit_target_data("ban", admin_ban_list + [user])
            await msg.finish(I18NContext("core.message.admin.ban.success"))
        else:
            await msg.finish(I18NContext("core.message.admin.ban.already"))
    if "unban" in msg.parsed_msg:
        if user in (banlist := admin_ban_list):
            banlist.remove(user)
            await msg.target_info.edit_target_data("ban", banlist)
            await msg.finish(I18NContext("core.message.admin.unban.success"))
        else:
            await msg.finish(I18NContext("core.message.admin.unban.none"))


locale = module(
    "locale", base=True, desc="{core.help.locale.desc}", alias="lang", doc=True
)


@locale.command()
async def _(msg: Bot.MessageSession):
    avaliable_lang = "[I18N:message.delimiter]".join(get_available_locales())
    res = [I18NContext("core.message.locale.prompt", lang="[I18N:language]"),
           I18NContext("core.message.locale.set.prompt", prefix=msg.prefixes[0]),
           I18NContext("core.message.locale.langlist", langlist=avaliable_lang)]

    if locale_url := Config("locale_url", locale_url_default, cfg_type=str):
        res.append(I18NContext("core.message.locale.contribute", url=locale_url))
    await msg.finish(res)


@locale.command("[<lang>] {{core.help.locale.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, lang: str):
    if lang in get_available_locales() and await msg.target_info.edit_attr("locale", lang):
        await msg.finish(Locale(lang).t("message.success"))
    else:
        avaliable_lang = "[I18N:message.delimiter]".join(get_available_locales())
        await msg.finish([I18NContext("core.message.locale.set.invalid"),
                          I18NContext("core.message.locale.langlist", langlist=avaliable_lang)])


@locale.command("reload", required_superuser=True)
async def _(msg: Bot.MessageSession):
    err = load_locale_file()
    if len(err) == 0:
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish([I18NContext("core.message.locale.reload.failed"), Plain("\n".join(err), disable_joke=True)])


whoami = module("whoami", base=True, doc=True)


@whoami.command("{{core.help.whoami}}")
async def _(msg: Bot.MessageSession):
    perm = []
    if await msg.check_native_permission():
        perm.append(I18NContext("core.message.whoami.admin"))
    elif await msg.check_permission():
        perm.append(I18NContext("core.message.whoami.botadmin"))
    if msg.check_super_user():
        perm.append(I18NContext("core.message.whoami.superuser"))
    await msg.finish([I18NContext("core.message.whoami", sender=msg.target.sender_id, target=msg.target.target_id, disable_joke=True)] + perm)


setup = module(
    "setup", base=True, desc="{core.help.setup.desc}", doc=True, alias="toggle"
)


@setup.command("typing {{core.help.setup.typing}}")
async def _(msg: Bot.MessageSession):
    if not msg.sender_data.get("disable_typing", False):
        await msg.sender_info.edit_sender_data("disable_typing", True)
        await msg.finish(I18NContext("core.message.setup.typing.disable"))
    else:
        await msg.sender_info.edit_sender_data("disable_typing", False)
        await msg.finish(I18NContext("core.message.setup.typing.enable"))


"""
@setup.command("check {{core.help.setup.check}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    if not msg.sender_data.get("typo_check", False):
        await msg.sender_info.edit_sender_data("typo_check", True)
        await msg.finish(I18NContext("core.message.setup.check.disable"))
    else:
        await msg.sender_info.edit_sender_data("typo_check", False)
        await msg.finish(I18NContext("core.message.setup.check.enable"))
"""


@setup.command(
    "timeoffset <offset> {{core.help.setup.timeoffset}}", required_admin=True
)
async def _(msg: Bot.MessageSession, offset: str):
    try:
        tstr_split = [int(part) for part in offset.split(":")]
        hour = tstr_split[0]
        minute = tstr_split[1] if len(tstr_split) > 1 else 0
        if hour > 12 or minute >= 60:
            raise ValueError
        offset = f"{hour:+}" if minute == 0 else f"{hour:+}:{abs(minute):02d}"
    except ValueError:
        await msg.finish(I18NContext("core.message.setup.timeoffset.invalid"))
    await msg.target_info.edit_target_data("timezone_offset", offset)
    await msg.finish(I18NContext("core.message.setup.timeoffset.success",
                                 offset="" if offset == "+0" else offset))


@setup.command("cooldown <second> {{core.help.setup.cooldown}}", required_admin=True)
async def _(msg: Bot.MessageSession, second: int):
    second = 0 if second < 0 else second
    await msg.target_info.edit_target_data("cooldown_time", second)
    await msg.finish(I18NContext("core.message.setup.cooldown.success", time=second))


mute = module(
    "mute", base=True, doc=True, required_admin=True, exclude_from=["TEST|Console"]
)


@mute.command("{{core.help.mute}}")
async def _(msg: Bot.MessageSession):
    state = await msg.target_info.switch_mute()
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


@leave.command("{{core.help.leave}}")
async def _(msg: Bot.MessageSession):
    confirm = await msg.wait_confirm(I18NContext("core.message.leave.confirm"))
    if confirm:
        await msg.send_message(I18NContext("core.message.leave.success"))
        await msg.call_api("set_group_leave", group_id=msg.session.target)
    else:
        await msg.finish()
