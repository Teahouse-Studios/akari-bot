from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.database.models import SenderUnionInfo

su = module("superuser", alias="su", required_superuser=True, base=True, doc=True)


@su.command("add <user> {{I18N:core.help.superuser.add}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    if await sender_union_info.edit_attr("superuser", True):
        await msg.finish(I18NContext("core.message.superuser.add.success", sender=user))


@su.command("remove <user> {{I18N:core.help.superuser.remove}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    if user == msg.session_info.sender_id:
        if not await msg.wait_confirm(I18NContext("core.message.superuser.remove.confirm"), append_instruction=False):
            await msg.finish()
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    if await sender_union_info.edit_attr("superuser", False):
        await msg.finish(I18NContext("core.message.superuser.remove.success", sender=user))
