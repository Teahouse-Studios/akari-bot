import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.utils.http import get_url

mojang_status = module(
    "mojang_status", desc="{I18N:mojang_status.help.desc}", alias=["mcstatus", "mjs", "mjsb"], developers=["Don_Trueno"]
)


@mojang_status.command()
async def _(msg: Bot.MessageSession):
    msg_list = [
        I18NContext(
            "mojang_status.message.status",
        )
    ]
    try:  # https://www.mcstate.net/docs#api-mojang-status
        data = orjson.loads(await get_url("https://www.mcstate.net/api/mojang-status", 200))
        for service in data.get("services", []):
            msg_list.append(
                I18NContext(
                    "mojang_status.message.status.each", api=service.get("label", ""), status=service.get("status", "")
                )
            )
    except ValueError as e:
        if str(e).startswith("429"):
            msg_list.append(I18NContext("mojang_status.message.failed"))
        else:
            raise e
    await msg.finish(msg_list)
