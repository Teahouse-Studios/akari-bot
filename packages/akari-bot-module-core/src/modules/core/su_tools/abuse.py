from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.database.models import SenderUnionInfo, TargetUnionInfo

ae = module("abuse", alias="ae", required_superuser=True, base=True, doc=True)


@ae.command("check <user> {{I18N:core.help.abuse.check}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    warns = sender_union_info.warns
    temp_banned_time = await Bot.Hook.trigger(
        "tos.check_temp_ban", session_info=msg.session_info, args={"target": user}
    )
    stat = []
    if temp_banned_time:
        stat.append(I18NContext("core.message.abuse.check.tempbanned", ban_time=temp_banned_time))
    if sender_union_info.trusted:
        stat.append(I18NContext("core.message.abuse.check.trusted"))
    elif sender_union_info.blocked:
        stat.append(I18NContext("core.message.abuse.check.banned"))
    await msg.finish([I18NContext("core.message.abuse.check.warns", sender=user, warns=warns)] + stat)


@ae.command("warn <user> [<count>] {{I18N:core.help.abuse.warn}}")
async def _(msg: Bot.MessageSession, user: str, count: int = 1):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    await sender_union_info.warn_user(count)
    warning_counts = await Bot.Hook.trigger("tos.warning_counts", session_info=msg.session_info)
    if sender_union_info.warns > warning_counts >= 1 and not sender_union_info.trusted:
        await sender_union_info.switch_identity(trust=False)
    await msg.finish(
        I18NContext("core.message.abuse.warn.success", sender=user, count=count, warn_count=sender_union_info.warns)
    )


@ae.command("revoke <user> [<count>] {{I18N:core.help.abuse.revoke}}")
async def _(msg: Bot.MessageSession, user: str, count: int = 1):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    await sender_union_info.warn_user(-count)
    await msg.finish(
        I18NContext("core.message.abuse.revoke.success", sender=user, count=count, warn_count=sender_union_info.warns)
    )


@ae.command("clear <user> {{I18N:core.help.abuse.clear}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    await sender_union_info.edit_attr("warns", 0)
    await msg.finish(I18NContext("core.message.abuse.clear.success", sender=user))


@ae.command("untempban <user> {{I18N:core.help.abuse.untempban}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    await Bot.Hook.trigger("tos.remove_temp_ban", session_info=msg.session_info, args={"target": user})
    await msg.finish(I18NContext("core.message.abuse.untempban.success", sender=user))


@ae.command("ban <user> {{I18N:core.help.abuse.ban}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    if await sender_union_info.switch_identity(trust=False, enable=True):
        await msg.finish(I18NContext("core.message.abuse.ban.success", sender=user))


@ae.command("unban <user> {{I18N:core.help.abuse.unban}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    if await sender_union_info.switch_identity(trust=False, enable=False):
        await msg.finish(I18NContext("core.message.abuse.unban.success", sender=user))


@ae.command("trust <user> {{I18N:core.help.abuse.trust}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    if await sender_union_info.switch_identity(trust=True, enable=True):
        await msg.finish(I18NContext("core.message.abuse.trust.success", sender=user))


@ae.command("distrust <user> {{I18N:core.help.abuse.distrust}}")
async def _(msg: Bot.MessageSession, user: str):
    if not Alive.determine_sender_from(user):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
            await msg.finish()
        sender_union_info = await SenderUnionInfo.resolve_union(user)
    if await sender_union_info.switch_identity(trust=True, enable=False):
        await msg.finish(I18NContext("core.message.abuse.distrust.success", sender=user))


@ae.command("block <target> {{I18N:core.help.abuse.block}}", available_for="QQ")
async def _(msg: Bot.MessageSession, target: str):
    if not target.startswith("QQ|Group|"):
        await msg.finish(I18NContext("message.id.invalid.target", target="QQ|Group"))
    if target == msg.session_info.target_id:
        await msg.finish(I18NContext("core.message.abuse.block.self"))
    target_union_info = await TargetUnionInfo.get_by_target_id(target, create=False)
    if not target_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.target.confirm"), append_instruction=False):
            await msg.finish()
        target_union_info = await TargetUnionInfo.resolve_union(target)
    if await target_union_info.edit_attr("blocked", True):
        await msg.finish(I18NContext("core.message.abuse.block.success", target=target))


@ae.command("unblock <target> {{I18N:core.help.abuse.unblock}}", available_for="QQ")
async def _(msg: Bot.MessageSession, target: str):
    if not target.startswith("QQ|Group|"):
        await msg.finish(I18NContext("message.id.invalid.target", target="QQ|Group"))
    target_union_info = await TargetUnionInfo.get_by_target_id(target, create=False)
    if not target_union_info:
        if not await msg.wait_confirm(I18NContext("message.id.init.target.confirm"), append_instruction=False):
            await msg.finish()
        target_union_info = await TargetUnionInfo.resolve_union(target)
    if await target_union_info.edit_attr("blocked", False):
        await msg.finish(I18NContext("core.message.abuse.unblock.success", target=target))
