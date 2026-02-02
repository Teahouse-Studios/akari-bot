import platform
import time

import psutil
from cpuinfo import get_cpu_info

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, FormattedTime, I18NContext, Url
from core.component import module
from core.config import Config
from core.constants.default import locale_url_default
from core.i18n import get_available_locales, Locale
from core.utils.bash import run_sys_command

ver = module("version", base=True, doc=True)


@ver.command("{{I18N:core.help.version}}")
async def _(msg: Bot.MessageSession):
    if Bot.Info.version:
        if str(Bot.Info.version).startswith("git:"):
            commit = Bot.Info.version[4:11]
            send_msgs = MessageChain.assign(I18NContext("core.message.version", version=commit, disable_joke=True))
            if Config("enable_commit_url", True):
                returncode, repo_url, _ = await run_sys_command(["git", "config", "--get", "remote.origin.url"])
                if returncode == 0:
                    repo_url = repo_url.strip().replace(".git", "")
                    commit_url = f"{repo_url}/commit/{commit}"
                    send_msgs.append(Url(commit_url, use_mm=False))
        else:
            version = Bot.Info.version
            send_msgs = MessageChain.assign(
                I18NContext(
                    "core.message.version",
                    version=version,
                    disable_joke=True))
            if Config("enable_commit_url", True):
                version = "nightly" if version.startswith("nightly") else version
                returncode, repo_url, _ = await run_sys_command(["git", "config", "--get", "remote.origin.url"])
                if returncode == 0:
                    repo_url = repo_url.strip().replace(".git", "")
                    commit_url = f"{repo_url}/releases/tag/{version}"
                    send_msgs.append(Url(commit_url, use_mm=False))
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
        result.append(I18NContext(
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
            disable_joke=True))
    else:
        disk_percent = psutil.disk_usage("/").percent
        result.append(I18NContext(
            "core.message.ping.simple",
            bot_running_time=timediff,
            cpu_percent=cpu_percent,
            ram_percent=ram_percent,
            disk_percent=disk_percent,
            disable_joke=True
        ))
    await msg.finish(result)


admin = module(
    "admin",
    base=True,
    required_admin=True,
    alias={"ban": "admin ban", "unban": "admin unban", "ban list": "admin ban list"},
    desc="{I18N:core.help.admin.desc}",
    doc=True
)


@admin.command(
    "add <user> {{I18N:core.help.admin.add}}",
    "remove <user> {{I18N:core.help.admin.remove}}",
    "list {{I18N:core.help.admin.list}}")
async def _(msg: Bot.MessageSession):
    if "list" in msg.parsed_msg:
        if msg.session_info.custom_admins:
            await msg.finish([I18NContext("core.message.admin.list")] + msg.session_info.custom_admins)
        else:
            await msg.finish(I18NContext("core.message.admin.list.none"))
    user = msg.parsed_msg["<user>"]
    if not user.startswith(f"{msg.session_info.sender_from}|"):
        await msg.finish(I18NContext("core.message.admin.invalid", sender=msg.session_info.sender_from,
                                     prefix=msg.session_info.prefixes[0]))
    if "add" in msg.parsed_msg:
        if user in msg.session_info.custom_admins:
            await msg.finish(I18NContext("core.message.admin.add.already"))
        if await msg.session_info.target_info.config_custom_admin(user):
            await msg.finish(I18NContext("core.message.admin.add.success", sender=user))
    if "remove" in msg.parsed_msg:
        if user == msg.session_info.sender_id:
            if not await msg.wait_confirm(I18NContext("core.message.admin.remove.confirm")):
                await msg.finish()
        if await msg.session_info.target_info.config_custom_admin(user, enable=False):
            await msg.finish(I18NContext("core.message.admin.remove.success", sender=user))


@admin.command(
    "ban <user> {{I18N:core.help.admin.ban}}",
    "unban <user> {{I18N:core.help.admin.unban}}",
    "ban list {{I18N:core.help.admin.ban.list}}",
)
async def _(msg: Bot.MessageSession):
    if "list" in msg.parsed_msg:
        if msg.session_info.banned_users:
            await msg.finish([I18NContext("core.message.admin.ban.list")] + msg.session_info.banned_users)
        else:
            await msg.finish(I18NContext("core.message.admin.ban.list.none"))
    user = msg.parsed_msg["<user>"]
    if not user.startswith(f"{msg.session_info.sender_from}|"):
        await msg.finish(I18NContext("core.message.admin.invalid", sender=msg.session_info.sender_from,
                                     prefix=msg.session_info.prefixes[0]))
    if "ban" in msg.parsed_msg:
        if user == msg.session_info.sender_id:
            await msg.finish(I18NContext("core.message.admin.ban.self"))
        if user in msg.session_info.banned_users:
            await msg.finish(I18NContext("core.message.admin.ban.already"))
        await msg.session_info.target_info.config_banned_user(user)
        await msg.finish(I18NContext("core.message.admin.ban.success", sender=user))
    if "unban" in msg.parsed_msg:
        if await msg.session_info.target_info.config_banned_user(user, enable=False):
            await msg.finish(I18NContext("core.message.admin.unban.success", sender=user))


locale = module(
    "locale", base=True, desc="{I18N:core.help.locale.desc}", alias="lang", doc=True
)


@locale.command()
async def _(msg: Bot.MessageSession):
    avaliable_lang = "{I18N:message.delimiter}".join(get_available_locales())
    res = [I18NContext("core.message.locale.prompt", lang="{I18N:language}"),
           I18NContext("core.message.locale.set.prompt", prefix=msg.session_info.prefixes[0]),
           I18NContext("core.message.locale.langlist", langlist=avaliable_lang)]

    if locale_url := Config("locale_url", locale_url_default, cfg_type=str):
        res.append(I18NContext("core.message.locale.contribute", url=locale_url))
    await msg.finish(res)


@locale.command("[<lang>] {{I18N:core.help.locale.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, lang: str):
    if lang in get_available_locales() and await msg.session_info.target_info.edit_attr("locale", lang):
        await msg.finish(Locale(lang).t("message.success"))
    else:
        avaliable_lang = "{I18N:message.delimiter}".join(get_available_locales())
        await msg.finish([I18NContext("core.message.locale.set.invalid"),
                          I18NContext("core.message.locale.langlist", langlist=avaliable_lang)])

"""
@locale.command("reload", required_superuser=True)
async def _(msg: Bot.MessageSession):
    err = load_locale_file()
    if len(err) == 0:
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish([I18NContext("core.message.locale.reload.failed"), Plain("\n".join(err), disable_joke=True)])
"""

whoami = module("whoami", base=True, doc=True)


@whoami.command("{{I18N:core.help.whoami}}")
async def _(msg: Bot.MessageSession):
    perm = []
    if await msg.check_native_permission():
        perm.append(I18NContext("core.message.whoami.admin"))
    elif await msg.check_permission():
        perm.append(I18NContext("core.message.whoami.botadmin"))
    if msg.check_super_user():
        perm.append(I18NContext("core.message.whoami.superuser"))
    await msg.finish(
        [I18NContext("core.message.whoami", sender=msg.session_info.sender_id, target=msg.session_info.target_id,
                     disable_joke=True)] + perm)


setup = module(
    "setup", base=True, desc="{I18N:core.help.setup.desc}", doc=True, alias="toggle"
)


@setup.command("typing {{I18N:core.help.setup.typing}}")
async def _(msg: Bot.MessageSession):
    if not msg.session_info.sender_info.sender_data.get("typing_prompt", True):
        await msg.session_info.sender_info.edit_sender_data("typing_prompt", True)
        await msg.finish(I18NContext("core.message.setup.typing.enable"))
    else:
        await msg.session_info.sender_info.edit_sender_data("typing_prompt", False)
        await msg.finish(I18NContext("core.message.setup.typing.disable"))


@setup.command("check {{I18N:core.help.setup.check}}")
async def _(msg: Bot.MessageSession):
    if not msg.session_info.sender_info.sender_data.get("typo_check", True):
        await msg.session_info.sender_info.edit_sender_data("typo_check", True)
        await msg.finish(I18NContext("core.message.setup.check.enable"))
    else:
        await msg.session_info.sender_info.edit_sender_data("typo_check", False)
        await msg.finish(I18NContext("core.message.setup.check.disable"))


@setup.command("sign {{I18N:core.help.setup.sign}}",
               required_admin=True,
               load=Config("enable_petal", False))
async def _(msg: Bot.MessageSession):
    if not msg.session_info.target_info.target_data.get("petal_sign", True):
        await msg.session_info.target_info.edit_target_data("petal_sign", True)
        await msg.finish(I18NContext("core.message.setup.sign.enable"))
    else:
        await msg.session_info.target_info.edit_target_data("petal_sign", False)
        await msg.finish(I18NContext("core.message.setup.sign.disable"))


@setup.command(
    "timeoffset <offset> {{I18N:core.help.setup.timeoffset}}", required_admin=True
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
    await msg.session_info.target_info.edit_target_data("timezone_offset", offset)
    await msg.finish(I18NContext("core.message.setup.timeoffset.success",
                                 offset="" if offset == "+0" else offset))


@setup.command("cooldown <second> {{I18N:core.help.setup.cooldown}}", required_admin=True)
async def _(msg: Bot.MessageSession, second: int):
    second = 0 if second < 0 else second
    await msg.session_info.target_info.edit_target_data("cooldown_time", second)
    await msg.finish(I18NContext("core.message.setup.cooldown.success", time=second))


mute = module("mute", base=True, doc=True, required_admin=True)


@mute.command("{{I18N:core.help.mute}}")
async def _(msg: Bot.MessageSession):
    state = await msg.session_info.target_info.switch_mute()
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
