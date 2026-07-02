import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.utils.http import get_url

mojang_status = module(
    "mojang_status", desc="{I18N:mojang_status.help.desc}", alias="mcstatus", developers=["Don_Trueno"]
)

MOJANG_SERVICES_ID = ["sessions", "api", "textures", "website", "accounts", "microsoft"]


@mojang_status.command()
async def _(msg: Bot.MessageSession):
    try:  # https://www.mcstate.net/docs#api-mojang-status
        data = orjson.loads(await get_url("https://www.mcstate.net/api/mojang-status", 200))
        msg_list = []
        for id in MOJANG_SERVICES_ID:
            status = data["services"][id]["status"]
            msg_list.append(I18NContext("mojang_status.message.status.each", api=id, status=status))
        message1 = "\n".join(msg_list)
    except ValueError as e:
        if str(e).startswith("429"):
            message1 = msg.session_info.locale.t("mojang_status.message.failed")
        else:
            raise e
    return I18NContext("mojang_status.message.status", statuses=message1)
