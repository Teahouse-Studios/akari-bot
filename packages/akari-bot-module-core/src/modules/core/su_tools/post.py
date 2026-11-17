from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.internal import I18NContext
from core.component import module

post_ = module("post", required_superuser=True, base=True, doc=True)


@post_.command("<target> <post_msg> {{I18N:core.help.post}}")
async def _(msg: Bot.MessageSession, target: str, post_msg: str):
    if not Alive.determine_target_from(target):
        await msg.finish(I18NContext("message.id.invalid.target", target=msg.session_info.target_from))
    session = await Bot.fetch_target(target, create=True)
    msg_chain = MessageChain.assign([I18NContext("core.message.post.prefix")] + match_kecode(post_msg))
    preview = msg_chain.copy()
    preview.insert(0, I18NContext("core.message.post.confirm", target=target))
    if await msg.wait_confirm(preview, append_instruction=False):
        await Bot.post_global_message(msg_chain, [session])
        await msg.finish(I18NContext("core.message.post.success"))
    else:
        await msg.finish()


@post_.command("global <post_msg> {{I18N:core.help.post.global}}")
async def _(msg: Bot.MessageSession, post_msg: str):
    msg_chain = MessageChain.assign([I18NContext("core.message.post.prefix")] + match_kecode(post_msg))
    preview = msg_chain.copy()
    preview.insert(0, I18NContext("core.message.post.global.confirm"))
    if await msg.wait_confirm(preview, append_instruction=False):
        await Bot.post_global_message(msg_chain)
        await msg.finish(I18NContext("core.message.post.success"))
    else:
        await msg.finish()
