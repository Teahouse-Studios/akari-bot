from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.utils.http import request_url

mojang_status = module(
    "mojang_status", desc="{I18N:mojang_status.help.desc}", alias=["mcstatus", "mjs", "mjsb"], developers=["Don_Trueno"]
)

url = {
    "account": "https://api.mojang.com",
    "session": "https://sessionserver.mojang.com",
    "services": "https://api.minecraftservices.com",
}


@mojang_status.command()
async def _(msg: Bot.MessageSession):
    msg_list = [
        I18NContext(
            "mojang_status.message.title",
        )
    ]
    for u, v in url.items():
        api = msg.session_info.locale.t("mojang_status.service." + u)
        try:
            DATA = await request_url(v, method="GET", logging_err_resp=False, attempt=1)
            if DATA is not None:
                status = msg.session_info.locale.t("mojang_status.status.online")
            else:
                status = msg.session_info.locale.t("mojang_status.status.empty")
        except ValueError as e:
            if str(e).startswith("40"):
                status = msg.session_info.locale.t("mojang_status.status.online")
            elif str(e).startswith("50"):
                status = msg.session_info.locale.t("mojang_status.status.offline")
            else:
                status = msg.session_info.locale.t("mojang_status.status.unknown")
        msg_list.append(I18NContext("mojang_status.message.entry", api=api, status=status))
    await msg.finish(msg_list)
