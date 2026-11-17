from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from modules.core.common_tools.bind import b


@b.command("whoami {{I18N:core.help.bind.whoami}}")
async def _(msg: Bot.MessageSession):
    sender_union_info = msg.session_info.sender_union_info
    target_union_info = msg.session_info.target_union_info

    msgchain = [
        I18NContext("core.message.bind.whoami.sender", id=msg.session_info.sender_id, disable_joke=True),
        I18NContext("core.message.bind.whoami.target", id=msg.session_info.target_id, disable_joke=True),
    ]

    if sender_union_info and msg.session_info.sender_id != sender_union_info.union_id:
        msgchain.append(
            I18NContext("core.message.bind.whoami.sender.union", id=sender_union_info.union_id, disable_joke=True)
        )
    if msg.session_info.target_id != target_union_info.union_id:
        msgchain.append(
            I18NContext("core.message.bind.whoami.target.union", id=target_union_info.union_id, disable_joke=True)
        )
    if await msg.check_native_permission():
        msgchain.append(I18NContext("core.message.bind.whoami.admin"))
    elif await msg.check_permission():
        msgchain.append(I18NContext("core.message.bind.whoami.botadmin"))
    if msg.check_super_user():
        msgchain.append(I18NContext("core.message.bind.whoami.superuser"))

    await msg.finish(msgchain)
