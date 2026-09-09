from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from core.component import module
from core.config.base import CoreConfig
from core.database.models import SenderUnionInfo
from core.scheduler import CronTrigger
from core.utils.petal import sign_get_petal, cost_petal
from core.utils.petal import settle_petals
from core.utils.bud import claim_bud, create_bud, find_bud, release_buds


petal_ = module(
    "petal", alias={"petals": "petal", "sign": "petal sign"}, base=True, doc=True, load=CoreConfig.enable_petal
)


@petal_.schedule(CronTrigger.from_crontab(CoreConfig.petal_reset_crontab))
async def _reset_petals():
    await settle_petals()


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


@petal_.command(
    [
        "[<user>] {{I18N:core.help.petal.admin}}",
        "modify <petal> [<user>] {{I18N:core.help.petal.modify}}",
        "clear [<user>] {{I18N:core.help.petal.clear}}",
    ],
    required_superuser=True,
)
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


@petal_.command("bud send <petal> <count> <passcode> {{I18N:core.help.petal.bud.send}}")
async def _(msg: Bot.MessageSession, petal: int, count: int, passcode: str):
    if petal <= 0:
        await msg.finish(I18NContext("petal.message.count.invalid"))
    if count <= 0 or petal < count:
        await msg.finish(I18NContext("core.message.petal.bud.count.invalid"))
    passcode = passcode.strip()
    if not await msg.wait_confirm(
        I18NContext("core.message.petal.bud.send.confirm", total=petal, count=count, code=passcode)
    ):
        await msg.finish()
    sender_union_info = msg.session_info.sender_union_info
    if not sender_union_info or not msg.session_info.sender_union_id:
        await msg.finish()
    if not await cost_petal(msg, petal):
        await msg.finish()
    bud = await create_bud(msg.session_info.sender_id, msg.session_info.sender_union_id, petal, count, passcode)
    if bud is None:
        await sender_union_info.modify_petal(petal)
        await msg.finish(I18NContext("core.message.petal.bud.code.exists"))
    await msg.finish(
        I18NContext(
            "core.message.petal.bud.send.success",
            id=bud["id"],
            total=petal,
            count=count,
            cmd=ActionText(f"{msg.session_info.prefixes[0]}petal bud {passcode}"),
        )
    )


@petal_.command("bud <passcode> {{I18N:core.help.petal.bud}}")
async def _(msg: Bot.MessageSession, passcode: str):
    status, _, amount = await claim_bud(msg, passcode.strip())
    if status == "success":
        await msg.finish(
            [
                I18NContext("core.message.petal.bud.receive.success"),
                I18NContext("petal.message.gained.success", amount=amount),
            ]
        )
    elif status == "already":
        await msg.finish(I18NContext("core.message.petal.bud.receive.already"))
    elif status == "empty":
        await msg.finish(I18NContext("core.message.petal.bud.receive.empty"))
    else:
        await msg.finish(I18NContext("core.message.petal.bud.receive.not_found"))


@petal_.command("bud info <id> {{I18N:core.help.petal.bud.info}}")
async def _(msg: Bot.MessageSession, id: str):
    bud = await find_bud(id.strip())
    if bud is None:
        await msg.finish(I18NContext("core.message.petal.bud.info.not_found"))
    records = bud["records"]
    lines = [
        I18NContext(
            "core.message.petal.bud.info",
            sender=bud["sender_id"],
            code=bud["code"],
            total=bud["total"],
            claimed=len(records),
            count=bud["count"],
        ),
    ]
    if not records:
        lines.append(I18NContext("none"))
    else:
        for r in records:
            lines.append(I18NContext("core.message.petal.bud.info.record", sender=r["sender_id"], amount=r["amount"]))
    await msg.finish(lines)


@petal_.command("bud release {{I18N:core.help.petal.bud.release}}", required_superuser=True)
async def _(msg: Bot.MessageSession):
    released = await release_buds()
    if released:
        await msg.finish(I18NContext("core.message.petal.bud.release", count=released))
    await msg.finish(I18NContext("core.message.petal.bud.release.none"))
