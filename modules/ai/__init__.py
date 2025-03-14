import io

from PIL import Image as PILImage

from core.builtins import Bot, I18NContext, Image, Plain
from core.component import module
from core.dirty_check import check_bool, rickroll
from core.utils.cooldown import CoolDown
from core.logger import Logger
from .formatting import generate_latex, generate_code_snippet
from .llm.claude import ask_claude
from .llm.openai import ask_chatgpt
from .llm.deepseek import ask_deepseek
# from .petal import count_token_petal

default_llm = "chatgpt"

ai = module("ai",
            developers=["Dianliang233", "DoroWolf"],
            desc="{ask.help.desc}",
            doc=True,
            exclude_from="QQBot",
            required_superuser=True)


@ai.command("<question> [--llm <llm>] {{ask.help}}",
            options_desc={"--llm": "{ai.help.option.llm}"})
async def _(msg: Bot.MessageSession, question: str):
    get_llm = msg.parsed_msg.get("--llm", False)
    llm = get_llm["<llm>"] if get_llm else None
    target_llm = msg.data.options.get("default_llm")
    is_superuser = msg.check_super_user()

#    if Config("enable_petal", False) and not is_superuser and msg.petal <= 0:
#        await msg.finish(msg.locale.t("petal.message.cost.not_enough"))

    qc = CoolDown("call_ai", msg, 60)
    c = qc.check()
    if c == 0 or msg.target.client_name == "TEST" or is_superuser:

        if await check_bool(question):
            await msg.finish(rickroll())
        if not llm:
            if target_llm:
                llm = target_llm
            else:
                llm = default_llm

        if llm == "chatgpt":
            blocks, tokens = await ask_chatgpt(msg, question)
        elif llm == "claude":
            blocks, tokens = await ask_claude(msg, question)
        elif llm == "deepseek":
            blocks, tokens = await ask_deepseek(msg, question)
        else:
            await msg.finish(msg.locale.t("ai.message.llm.invalid"))

        Logger.info(tokens)
#        petal = await count_token_petal(msg, tokens)
        chain = []
        for block in blocks:
            if block["type"] == "text":
                chain.append(Plain(block["content"]))
            elif block["type"] == "latex":
                content = block["content"]
                try:
                    content = await generate_latex(content)
                    img = PILImage.open(io.BytesIO(content))
                    chain.append(Image(img))
                except Exception:
                    chain.append(I18NContext("ask.message.text2img.error", text=content))
            elif block["type"] == "code":
                content = block["content"]["code"]
                try:
                    content = await generate_code_snippet(content, block["content"]["language"])
                    img = PILImage.open(io.BytesIO(content))
                    chain.append(Image(img))
                except Exception:
                    chain.append(I18NContext("ask.message.text2img.error", text=content))

#        if petal != 0:
#            chain.append(I18NContext("petal.message.cost", amount=petal))

        if msg.target.client_name != "TEST" and not is_superuser:
            qc.reset()
        await msg.finish(chain)
    else:
        await msg.finish(msg.locale.t("message.cooldown", time=int(c)))


@ai.command("set <llm> {{ai.help.set}}")
async def _(msg: Bot.MessageSession, llm: str):
    msg.data.edit_option("ai_default_llm", llm)
    await msg.finish(msg.locale.t("success"))
