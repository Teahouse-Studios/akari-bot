import asyncio
import re

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.dirty_check import check
from .server import query_java_server, query_bedrock_server

s = module(
    "mcserver",
    alias="server",
    developers=["_LittleC_", "OasisAkari", "DoroWolf"],
    doc=True,
)


@s.command(
    "<address:port> [-r] [-p] {{I18N:server.help}}",
    options_desc={"-r": "{I18N:server.help.option.r}",
                  "-p": "{I18N:server.help.option.p}"}
)
async def _(msg: Bot.MessageSession):
    server_address = msg.parsed_msg["<address:port>"]
    raw = msg.parsed_msg.get("-r", False)
    showplayer = msg.parsed_msg.get("-p", False)

    if check_local_address(server_address):
        await msg.finish(I18NContext("server.message.local_address"))

    java_info, bedrock_info = await asyncio.gather(
        query_java_server(server_address, raw, showplayer),
        query_bedrock_server(server_address, raw),
    )

    sendmsg = [java_info, bedrock_info]
    if sendmsg == ["", ""]:
        await msg.finish(I18NContext("server.message.not_found"))
    else:
        sendmsg = "\n".join(sendmsg).split("\n")
        sendmsg = await check(sendmsg, session=msg)
        t = "\n".join(x["content"] for x in sendmsg)
        await msg.finish(t.strip())


def check_local_address(server_address):
    if "localhost" in server_address.lower():
        return True

    match_serip = re.match(r"(.*?)\.(.*?)\.(.*?)\.(.*?)", server_address)
    if match_serip:
        if match_serip.group(1) == "192":
            if match_serip.group(2) == "168":
                return True
        if match_serip.group(1) == "172":
            if 16 <= int(match_serip.group(2)) <= 31:
                return True
        if match_serip.group(1) == "10":
            if 0 <= int(match_serip.group(2)) <= 255:
                return True
        if match_serip.group(1) == "127":
            return True
        if match_serip.group(1) == "0":
            if match_serip.group(2) == "0":
                if match_serip.group(3) == "0":
                    return True
    return False
