from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.utils.random import Random

import asyncio

bc = module("connect", base=True)
bind_tokens = {}


@bc.command("link", required_admin=True, available_for=["QQ|Group"])
async def _(msg: Bot.MessageSession):
    if await msg.wait_confirm(I18NContext("core.message.connect.link.confirm")):
        bk = Random.randstr(20)
        bv = Random.randstr(20)
        bind_tokens[bk] = {"v": bv, "a_msg": msg}
        await msg.send_message(f"{msg.session_info.prefixes[0]}connect token {bk}")
        await msg.hold()

        async def timeout_session():
            await asyncio.sleep(30)
            if bk in bind_tokens:
                await msg.send_message(I18NContext("core.message.connect.link.timeout"))
                del bind_tokens[bk]
                await msg.release()

        asyncio.create_task(timeout_session())


@bc.command("token <t>")
async def _(msg: Bot.MessageSession):
    if (t := msg.parsed_msg.get("<t>")) in bind_tokens:
        bind_tokens[t]["b_msg"] = msg
        bind_tokens[t]["a_in_b_client_id"] = msg.session_info.sender_id
        await msg.send_message(f"{msg.session_info.prefixes[0]}connect bind {bind_tokens[t].get('v')}")
        await msg.hold()


@bc.command("bind <v>")
async def _(msg: Bot.MessageSession):
    # todo ...会出现一个会话有三个小可的情况吗？
    for k, v in bind_tokens.copy().items():
        if v.get("v") == msg.parsed_msg.get("<v>"):
            bind_tokens[k]["b_in_a_client_id"] = msg.session_info.sender_id
            a_msg: Bot.MessageSession = v.get("a_msg")
            b_msg: Bot.MessageSession = v.get("b_msg")

            try:
                a_connected_sessions = a_msg.session_info.target_info.target_data.get("connected_session", [])
                b_connected_sessions = b_msg.session_info.target_info.target_data.get("connected_session", [])
                a_bots_id = a_msg.session_info.target_info.target_data.get("bots_id", [])
                b_bots_id = b_msg.session_info.target_info.target_data.get("bots_id", [])
                if a_msg.session_info.target_id not in b_connected_sessions:
                    b_connected_sessions.append(a_msg.session_info.target_id)
                    b_bots_id.append(bind_tokens[k]["a_in_b_client_id"])
                    await b_msg.session_info.target_info.edit_target_data("connected_session", b_connected_sessions)
                    await a_msg.session_info.target_info.edit_target_data("bots_id", a_bots_id)
                    await b_msg.send_message(
                        I18NContext(
                            "core.message.connect.bind.success",
                            target_a=b_msg.session_info.target_id,
                            target_b=a_msg.session_info.target_id,
                        )
                    )

                if b_msg.session_info.target_id not in a_connected_sessions:
                    a_connected_sessions.append(b_msg.session_info.target_id)
                    a_bots_id.append(bind_tokens[k]["b_in_a_client_id"])
                    await a_msg.session_info.target_info.edit_target_data("connected_session", a_connected_sessions)
                    await b_msg.session_info.target_info.edit_target_data("bots_id", b_bots_id)
                    await a_msg.send_message(
                        I18NContext(
                            "core.message.connect.bind.success",
                            target_a=a_msg.session_info.target_id,
                            target_b=b_msg.session_info.target_id,
                        )
                    )

            finally:
                del bind_tokens[k]
                await a_msg.release()
                await b_msg.release()


@bc.command("clear")
async def _(msg: Bot.MessageSession):
    if await msg.wait_confirm(I18NContext("core.message.connect.clear.confirm")):
        await msg.session_info.target_info.edit_target_data("connected_session", [])
        await msg.session_info.target_info.edit_target_data("bots_id", [])
        await msg.send_message(I18NContext("core.message.connect.clear.success"))
