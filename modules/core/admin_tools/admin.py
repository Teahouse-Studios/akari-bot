from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from core.component import module
from core.database.models import SenderUnionBind, SenderUnionInfo

admin = module(
    "admin",
    base=True,
    required_admin=True,
    alias={
        "ban": "admin ban",
        "unban": "admin unban",
        "ban list": "admin ban list",
        "leave": "admin leave",
        "dismiss": "admin leave",
    },
    desc="{I18N:core.help.admin.desc}",
    doc=True,
)


async def _display_union_list(msg: Bot.MessageSession, union_ids: list[str]) -> list[str]:
    delimiter = str(I18NContext("message.delimiter"))
    lines = []
    for union_id in union_ids:
        bound_ids = await SenderUnionBind.list_ids(union_id)
        lines.append(delimiter.join(bound_ids) if bound_ids else union_id)
    return lines


async def _resolve_union_id(user: str, create: bool = True) -> str:
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


@admin.command("leave {{I18N:core.help.admin.leave}}", available_for="QQ|Group")
async def _(msg: Bot.MessageSession):
    if await msg.wait_confirm(I18NContext("core.message.admin.leave.confirm")):
        await msg.send_message(I18NContext("core.message.admin.leave.success"))
        await msg.call_onebot_api("set_group_leave", group_id=int(msg.session_info.get_common_target_id()))
    else:
        await msg.finish()
