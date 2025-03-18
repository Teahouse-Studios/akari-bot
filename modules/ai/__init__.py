import io

from PIL import Image as PILImage

from core.builtins import Bot, I18NContext, Image, Plain
from core.component import module
from core.config import Config
from core.dirty_check import check_bool, rickroll
from core.utils.cooldown import CoolDown
from core.logger import Logger
from .formatting import generate_code_snippet, generate_latex, generate_md_table
from .llm import ask_llm
from .setting import *
# from .petal import count_token_petal

default_llm = Config("ai_default_llm", cfg_type=str, table_name="module_ai")
default_llm = default_llm if default_llm in llm_list else None


ai = module("ai",
            developers=["DoroWolf", "Dianliang233"],
            desc="{ai.help.desc}",
            doc=True,
            exclude_from="QQBot",
            required_superuser=True)


@ai.command("<question> [--llm <llm>] {{ai.help}}",
            options_desc={"--llm": "{ai.help.option.llm}"})
async def _(msg: Bot.MessageSession, question: str):
    get_llm = msg.parsed_msg.get("--llm", False)
    llm = get_llm["<llm>"].lower() if get_llm else None
    target_llm = msg.data.options.get("ai_default_llm")
    is_superuser = msg.check_super_user()

#    if Config("enable_petal", False) and not is_superuser and msg.petal <= 0:
#        await msg.finish(msg.locale.t("petal.message.cost.not_enough"))

    qc = CoolDown("call_ai", msg, 60)
    c = qc.check()
    if c == 0 or msg.target.client_name == "TEST" or is_superuser:

        if await check_bool(question):
            await msg.finish(rickroll())

        avaliable_llms = llm_list + (llm_su_list if is_superuser else [])

        if not llm:
            llm = target_llm if target_llm else default_llm

        llm_info = None
        if llm in avaliable_llms:
            llm_info = next(l for l in llm_api_list if l["name"] == llm)
        if llm_info:
            blocks, tokens = await ask_llm(question, llm_info["model_name"], llm_info["api_url"], llm_info["api_key"])
        else:
            await msg.finish(msg.locale.t("ai.message.llm.invalid"))

        Logger.debug(blocks)
        Logger.info(f"{tokens} tokens used while calling AI.")
#        petal = await count_token_petal(msg, tokens)

        chain = []
        for block in blocks:
            if block["type"] == "text":
                chain.append(Plain(block["content"]))
            elif block["type"] == "latex":
                content = block["content"]
                try:
                    path = generate_latex(content)
                    chain.append(Image(path))
                except Exception:
                    chain.append(I18NContext("ai.message.text2img.error", text=content))
            elif block["type"] == "code":
                content = block["content"]["code"]
                try:
                    content = await generate_code_snippet(content, block["content"]["language"])
                    img = PILImage.open(io.BytesIO(content))
                    chain.append(Image(img))
                except Exception:
                    chain.append(I18NContext("ai.message.text2img.error", text=content))
            elif block["type"] == "table":
                content = block["content"]
                try:
                    path_lst = await generate_md_table(content)
                    for path in path_lst:
                        chain.append(Image(path))
                except Exception:
                    chain.append(I18NContext("ai.message.text2img.error", text=content))

#        if petal != 0:
#            chain.append(I18NContext("petal.message.cost", amount=petal))

        if msg.target.client_name != "TEST" and not is_superuser:
            qc.reset()
        await msg.finish(chain)
    else:
        await msg.finish(msg.locale.t("message.cooldown", time=int(c)))


@ai.command("set <llm> {{ai.help.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, llm: str):
    llm = llm.lower()
    if llm in llm_list:
        msg.data.edit_option("ai_default_llm", llm)
        await msg.finish(msg.locale.t("message.success"))
    else:
        await msg.finish(msg.locale.t("ai.message.llm.invalid"))


@ai.command("list {{ai.help.list}}")
async def _(msg: Bot.MessageSession):
    avaliable_llms = llm_list + (llm_su_list if msg.check_super_user() else [])

    if avaliable_llms:
        await msg.finish(f"{msg.locale.t('ai.message.list.prompt')}\n{'\n'.join(avaliable_llms)}")
    else:
        await msg.finish(msg.locale.t("ai.message.list.none"))
