from core.builtins import Bot, I18NContext, Plain
from core.component import module
from core.config import Config
from core.dirty_check import check_bool, rickroll
from core.utils.cooldown import CoolDown
from core.logger import Logger
from .llm import ask_llm
from .setting import llm_api_list, llm_list, llm_su_list
from .petal import precount_petal, count_token_petal

default_llm = Config("ai_default_llm", cfg_type=str, table_name="module_ai")
default_llm = default_llm if default_llm in llm_list else None


ai = module("ai",
            developers=["DoroWolf", "Dianliang233"],
            desc="{ai.help.desc}",
            doc=True,
            exclude_from="QQBot")


@ai.command("<question> [--llm <llm>] {{ai.help}}",
            options_desc={"--llm": "{ai.help.option.llm}"})
async def _(msg: Bot.MessageSession, question: str):
    get_llm = msg.parsed_msg.get("--llm", False)
    llm = get_llm["<llm>"].lower() if get_llm else None
    target_llm = msg.target_data.get("ai_default_llm")
    is_superuser = msg.check_super_user()

    avaliable_llms = llm_list + (llm_su_list if is_superuser else [])

    if not llm:
        llm = target_llm if target_llm else default_llm

    llm_info = None
    if llm in avaliable_llms:
        llm_info = next((l for l in llm_api_list if l["name"] == llm), None)

    if llm_info:
        if not is_superuser and not precount_petal(msg, llm_info["price_in"], llm_info["price_out"]):
            await msg.finish(I18NContext("petal.message.cost.not_enough"))

        if await check_bool(question):
            await msg.finish(rickroll())

        qc = CoolDown("call_ai", msg, 60)
        c = qc.check()
        if c == 0 or msg.target.client_name == "TEST" or is_superuser:
            chain, input_tokens, output_tokens = await ask_llm(question, llm_info["model_name"], llm_info["api_url"], llm_info["api_key"])

            Logger.info(f"{input_tokens + output_tokens} tokens used while calling AI.")
            petal = await count_token_petal(msg, llm_info["price_in"], llm_info["price_out"], input_tokens, output_tokens)

            if petal != 0:
                chain.append(I18NContext("petal.message.cost", amount=petal))

            if msg.target.client_name != "TEST" and not is_superuser:
                qc.reset()
            await msg.finish(chain)
        else:
            await msg.finish(I18NContext("message.cooldown", time=int(c)))
    else:
        await msg.finish(I18NContext("ai.message.llm.invalid"))


@ai.command("set <llm> {{ai.help.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, llm: str):
    llm = llm.lower()
    if llm in llm_list:
        await msg.target_info.edit_target_data("ai_default_llm", llm)
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(I18NContext("ai.message.llm.invalid"))


@ai.command("list {{ai.help.list}}")
async def _(msg: Bot.MessageSession):
    avaliable_llms = llm_list + (llm_su_list if msg.check_super_user() else [])

    if avaliable_llms:
        await msg.finish([I18NContext("ai.message.list"), Plain("\n".join(sorted(avaliable_llms))), I18NContext("ai.message.list.prompt", prefix=msg.prefixes[0])])
    else:
        await msg.finish(I18NContext("ai.message.list.none"))
