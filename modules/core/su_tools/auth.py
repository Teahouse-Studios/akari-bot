from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.database.models import SenderUnionInfo
from core.loader import ModulesManager

auth = module("auth", required_superuser=True, base=True, doc=True)


def _get_authorizations(sender_union_info: SenderUnionInfo) -> list[dict]:
    return sender_union_info.sender_data.get("module_auth", [])


def _set_authorizations(sender_union_info: SenderUnionInfo, auth_list: list[dict]):
    return sender_union_info.edit_sender_data("module_auth", auth_list)


async def _check_authorizer_still_superuser(authorized_by: str) -> bool:
    authorizer = await SenderUnionInfo.get_by_sender_id(authorized_by, create=False)
    return bool(authorizer and authorizer.superuser)


@auth.command(
    "add <user> <module> {{I18N:core.help.auth.add}}",
    "remove <user> <module> {{I18N:core.help.auth.remove}}",
)
async def _(msg: Bot.MessageSession, user: str, module: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    target_module = ModulesManager.modules.get(module)
    if not target_module:
        await msg.finish(I18NContext("core.message.auth.module_not_found", module=module))
    if not target_module.required_superuser:
        await msg.finish(I18NContext("core.message.auth.module_not_required_superuser", module=module))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    auth_list = _get_authorizations(sender_union_info)
    if "add" in msg.parsed_msg:
        verify = await msg.verify_user()
        if verify:
            for entry in auth_list:
                if entry["module"] == module and entry["authorized_by"] == msg.session_info.sender_id:
                    await msg.finish(I18NContext("core.message.auth.add.already", user=user, module=module))
                    return
            auth_list.append({"module": module, "authorized_by": msg.session_info.sender_id})
            await _set_authorizations(sender_union_info, auth_list)
            await msg.finish(I18NContext("core.message.auth.add.success", user=user, module=module))
    elif "remove" in msg.parsed_msg:
        new_list = [
            e for e in auth_list if not (e["module"] == module and e["authorized_by"] == msg.session_info.sender_id)
        ]
        if len(new_list) == len(auth_list):
            await msg.finish(I18NContext("core.message.auth.remove.not_found", user=user, module=module))
            return
        await _set_authorizations(sender_union_info, new_list)
        await msg.finish(I18NContext("core.message.auth.remove.success", user=user, module=module))


@auth.command("list <user> {{I18N:core.help.auth.list}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        await msg.finish(I18NContext("core.message.auth.list.empty"))
        return
    auth_list = _get_authorizations(sender_union_info)
    if not auth_list:
        await msg.finish(I18NContext("core.message.auth.list.empty"))
        return
    lines = []
    for entry in auth_list:
        lines.append(
            I18NContext(
                "core.message.auth.list.entry",
                user=user,
                module=entry["module"],
                authorized_by=entry["authorized_by"],
            )
        )
    await msg.finish(lines)
