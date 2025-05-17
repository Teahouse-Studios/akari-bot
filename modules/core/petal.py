from core.builtins import Bot, I18NContext
from core.config import Config
from core.component import module
from core.database.models import SenderInfo
from core.utils.info import get_all_sender_prefix
from core.utils.petal import sign_get_petal, cost_petal

sender_list = get_all_sender_prefix()

petal_ = module("petal",
                alias={
                    "petals": "petal",
                    "sign": "petal sign"
                },
                base=True,
                doc=True,
                load=Config("enable_petal", False)
                )


@petal_.command("{[I18N:core.help.petal]}")
async def _(msg: Bot.MessageSession):
    await msg.finish(I18NContext("core.message.petal.self", petal=msg.petal))


@petal_.command("sign {[I18N:core.help.petal.sign]}")
async def _(msg: Bot.MessageSession):
    amount = await sign_get_petal(msg)
    if amount:
        await msg.finish([I18NContext("core.message.petal.sign.success"),
                          I18NContext("petal.message.gained.success", amount=amount)])
    else:
        await msg.finish(I18NContext("core.message.petal.sign.already"))


@petal_.command("give <petal> <user> {[I18N:core.help.petal.give]}")
async def _(msg: Bot.MessageSession, petal: int, user: str):
    if petal <= 0:
        await msg.finish(I18NContext("petal.message.count.invalid"))
    if not user.startswith(f"{msg.target.client_name}|"):
        await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.target.sender_from))
    if user == msg.target.sender_id:
        await msg.finish(I18NContext("core.message.petal.give.self"))
    sender_info = await SenderInfo.get_by_sender_id(user, create=False)
    if not sender_info:
        await msg.finish(I18NContext("message.id.not_found.sender"))
    if await msg.wait_confirm(I18NContext("core.message.petal.give.confirm", sender=user, give_petal=petal)):
        if cost_petal(msg, petal):
            await sender_info.modify_petal(petal)
            await msg.finish(I18NContext("core.message.petal.give.success", sender=user, give_petal=petal, petal=sender_info.petal))
        else:
            await msg.finish()
    else:
        await msg.finish()


@petal_.command(["[<user>]",
                 "modify <petal> [<user>]",
                 "clear [<user>]"],
                required_superuser=True)
async def _(msg: Bot.MessageSession):
    user = msg.parsed_msg.get("<user>", False)
    if msg.parsed_msg.get("modify", False):
        petal = msg.parsed_msg.get("<petal>", False)
        if user:
            if not any(user.startswith(f"{sender_from}|") for sender_from in sender_list):
                await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.target.sender_from))
            sender_info = await SenderInfo.get_by_sender_id(user)
            await sender_info.modify_petal(petal)
            await msg.finish(I18NContext("core.message.petal.modify", sender=user, add_petal=petal, petal=sender_info.petal))
        else:
            await msg.sender_info.modify_petal(petal)
            await msg.finish(I18NContext("core.message.petal.modify.self", add_petal=petal, petal=sender_info.petal))
    elif msg.parsed_msg.get("clear", False):
        if user:
            if not any(user.startswith(f"{sender_from}|") for sender_from in sender_list):
                await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.target.sender_from))
            sender_info = await SenderInfo.get_by_sender_id(user, create=False)
            if not sender_info:
                if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
                    await msg.finish()
                await SenderInfo.create(sender_id=user)
            await sender_info.clear_petal()
            await msg.finish(I18NContext("core.message.petal.clear", sender=user))
        else:
            await msg.sender_info.clear_petal()
            await msg.finish(I18NContext("core.message.petal.clear.self"))
    else:
        if user:
            if not any(user.startswith(f"{sender_from}|") for sender_from in sender_list):
                await msg.finish(I18NContext("message.id.invalid.sender", sender=msg.target.sender_from))
            sender_info = await SenderInfo.get_by_sender_id(user, create=False)
            if not sender_info:
                if not await msg.wait_confirm(I18NContext("message.id.init.sender.confirm"), append_instruction=False):
                    await msg.finish()
                await SenderInfo.create(sender_id=user)
            await msg.finish(I18NContext("core.message.petal", sender=user, petal=sender_info.petal))
        else:
            await msg.finish(I18NContext("core.message.petal.self", petal=msg.petal))
