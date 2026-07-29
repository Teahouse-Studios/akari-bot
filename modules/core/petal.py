from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.config.base import CoreConfig
from core.database.models import SenderUnionInfo
from core.utils.petal import sign_get_petal, cost_petal

petal_ = module(
    "petal", alias={"petals": "petal", "sign": "petal sign"}, base=True, doc=True, load=CoreConfig.enable_petal
)


@petal_.command("{{I18N:core.help.petal}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(I18NContext("core.message.petal.self", petal=msg.session_info.petal))


@petal_.command("sign {{I18N:core.help.petal.sign}}")
async def _(msg: Bot.MessageSession):
    if msg.session_info.target_union_info.target_data.get("petal_sign", True):
        amount = await sign_get_petal(msg)
        if amount:
            await msg.finish(
                [
                    I18NContext("core.message.petal.sign.success"),
                    I18NContext("petal.message.gained.success", amount=amount),
                ]
            )
        else:
            await msg.finish(I18NContext("core.message.petal.sign.already"))
    else:
        await msg.finish(I18NContext("core.message.petal.sign.disabled"))


@petal_.command("give <petal> <user> {{I18N:core.help.petal.give}}")
async def _(msg: Bot.MessageSession, petal: int, user: str):
    if petal <= 0:
        await msg.finish(I18NContext("petal.message.count.invalid"))
    if not user.startswith(f"{msg.session_info.client_name}|"):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
    if user == msg.session_info.sender_id:
        await msg.finish(I18NContext("core.message.petal.give.self"))
    sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
    if not sender_union_info:
        await msg.finish(I18NContext("message.id.not_found.sender"))
    if await msg.wait_confirm(I18NContext("core.message.petal.give.confirm", sender=user, give_petal=petal)):
        if await cost_petal(msg, petal):
            await sender_union_info.modify_petal(petal)
            await msg.finish(
                I18NContext(
                    "core.message.petal.give.success",
                    sender=user,
                    give_petal=petal,
                    petal=msg.session_info.petal - int(petal),
                )
            )
        else:
            await msg.finish()
    else:
        await msg.finish()


@petal_.command(["[<user>]", "modify <petal> [<user>]", "clear [<user>]"], required_superuser=True)
async def _(msg: Bot.MessageSession):
    user = msg.parsed_msg.get("<user>", False)
    if msg.parsed_msg.get("modify", False):
        petal = msg.parsed_msg.get("<petal>", False)
        if user:
            if not Alive.determine_sender_from(user):
                await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
            sender_union_info = await SenderUnionInfo.get_by_sender_id(user)
            await sender_union_info.modify_petal(petal)
            await msg.finish(
                I18NContext("core.message.petal.modify", sender=user, add_petal=petal, petal=sender_union_info.petal)
            )
        else:
            await msg.session_info.sender_union_info.modify_petal(petal)
            await msg.finish(
                I18NContext(
                    "core.message.petal.modify.self", add_petal=petal, petal=msg.session_info.petal + int(petal)
                )
            )
    elif msg.parsed_msg.get("clear", False):
        if user:
            if not Alive.determine_sender_from(user):
                await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
            sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
            if not sender_union_info:
                if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
                    await msg.finish()
                sender_union_info = await SenderUnionInfo.resolve_union(user)
            await sender_union_info.clear_petal()
            await msg.finish(I18NContext("core.message.petal.clear", sender=user))
        else:
            await msg.session_info.sender_union_info.clear_petal()
            await msg.finish(I18NContext("core.message.petal.clear.self"))
    else:
        if user:
            if not Alive.determine_sender_from(user):
                await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.session_info.sender_from))
            sender_union_info = await SenderUnionInfo.get_by_sender_id(user, create=False)
            if not sender_union_info:
                if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
                    await msg.finish()
                sender_union_info = await SenderUnionInfo.resolve_union(user)
            await msg.finish(I18NContext("core.message.petal", sender=user, petal=sender_union_info.petal))
        else:
            await msg.finish(I18NContext("core.message.petal.self", petal=msg.session_info.petal))
