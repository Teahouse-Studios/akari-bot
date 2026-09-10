from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext, ImageElement, Plain
from core.builtins.message.chain import MessageChain
from core.component import module
from modules.ai.config import AiConfig
from core.utils.cooldown import CoolDown
from core.utils.dirty_check import check_bool, rickroll
from core.logger import Logger
from core.constants import WaitCancelException
from .petal import precount_petal, count_token_petal
from .setting import get_llm_billing, llm_api_list, llm_list, llm_su_list
from .context import CONTEXT_EXPIRY, create_context, get_context

default_llm = AiConfig.ai_default_llm
default_llm = default_llm if default_llm in llm_list else None

ai = module("ai", developers=["DoroWolf", "Dianliang233"], desc="{I18N:ai.help.desc}", doc=True)


@ai.command(
    "<prompt> [--ctx <turn_id>] [--llm <llm>] [--no-tools] {{I18N:ai.help}}",
    options_desc={
        "--ctx": "{I18N:ai.help.option.ctx}",
        "--llm": "{I18N:ai.help.option.llm}",
        "--no-tools": "{I18N:ai.help.option.no_tools}",
    },
)
async def _(msg: Bot.MessageSession, prompt: str):
    get_ctx = msg.parsed_msg.get("--ctx", False)
    turn_id = get_ctx["<turn_id>"].strip() if get_ctx else None
    get_llm = msg.parsed_msg.get("--llm", False)
    selected_llm = get_llm["<llm>"].lower() if get_llm else None
    target_default_llm = msg.session_info.target_union_info.target_data.get("ai_default_llm")
    use_tools = not msg.parsed_msg.get("--no-tools", False)

    is_superuser = msg.check_super_user()

    context_key = msg.session_info.channel_key
    history = get_context(turn_id, context_key) if turn_id else None
    if turn_id and history is None:
        await msg.finish(I18NContext("ai.message.context.invalid"))

    available_llms = llm_list + (llm_su_list if is_superuser else [])

    if not selected_llm:
        selected_llm = target_default_llm if target_default_llm else default_llm

    llm_info = None
    if selected_llm in available_llms:
        llm_info = next((llm for llm in llm_api_list if llm["name"].lower() == selected_llm), None)

    if not llm_info:
        await msg.finish(I18NContext("ai.message.llm.invalid"))

    current_msg = msg
    current_prompt = prompt

    while True:
        current_is_superuser = current_msg.check_super_user()

        billing = get_llm_billing(llm_info)
        if not current_is_superuser and not precount_petal(
            current_msg,
            billing["input_price"],
            billing["cache_price"],
            billing["output_price"],
            call_price=billing["call_price"],
        ):
            await current_msg.finish(I18NContext("petal.message.cost.not_enough"))

        if await check_bool(current_prompt, current_msg):
            await current_msg.finish(rickroll())

        qc = CoolDown("call_ai", current_msg, 60)
        c = qc.check()
        if c != 0 and not current_is_superuser:
            await current_msg.finish(I18NContext("message.cooldown", time=int(c)))

        # OpenAI、Matplotlib、网页提取等依赖体积较大，仅在实际调用 AI 时加载。
        from .llm import ask_llm

        prompt_chain = MessageChain.assign(
            [
                Plain(current_prompt),
                *(x for x in current_msg.session_info.messages.values if isinstance(x, ImageElement)),
            ]
        )
        chain, input_tokens, cache_tokens, output_tokens, history = await ask_llm(
            current_msg,
            prompt_chain,
            llm_info["model_name"],
            llm_info["api_url"],
            llm_info["api_key"],
            use_tools,
            history=history,
        )

        # 每轮建立新的快照，保留旧 ID 以支持从任意一轮分叉。
        turn_id = create_context(history, context_key)

        Logger.info(f"{input_tokens + cache_tokens + output_tokens} token used while calling LLM.")
        Logger.info(f"Input (miss cache): {input_tokens} | Input (hit cache): {cache_tokens} | Output: {output_tokens}")
        billing = get_llm_billing(llm_info, input_tokens)
        petal = await count_token_petal(
            current_msg,
            billing["input_price"],
            billing["cache_price"],
            billing["output_price"],
            input_tokens,
            cache_tokens,
            output_tokens,
            billing["call_price"],
        )

        chain.append(Plain("\n---\n"))
        cmd = ActionText(f"{msg.session_info.prefixes[0]}ai --ctx {turn_id}")
        if msg.session_info.support_quote:
            chain.append(I18NContext("ai.message.context.hint.quote", cmd=cmd))
        else:
            chain.append(I18NContext("ai.message.context.hint", cmd=cmd))
        chain.append(I18NContext("ai.message.context.id", turn_id=turn_id))
        if petal != 0:
            chain.append(I18NContext("petal.message.cost", amount=petal))

        if not current_is_superuser:
            qc.reset()

        if not msg.session_info.support_quote:
            await current_msg.finish(chain)

        try:
            reply = await current_msg.wait_reply(chain, all_=True, timeout=CONTEXT_EXPIRY, append_instruction=False)
        except WaitCancelException:
            await msg.finish()

        current_prompt = reply.as_display(text_only=True).strip()
        current_msg = reply
        if not current_prompt and not any(isinstance(x, ImageElement) for x in reply.session_info.messages.values):
            await msg.finish()


@ai.command("llm instruct [<instructions>] {{I18N:ai.help.llm.instruct}}")
async def _(msg: Bot.MessageSession, llm: str):
    instructions = msg.parsed_msg.get("<instructions>")
    await msg.session_info.sender_union_info.edit_sender_data("ai_custom_instructions", instructions)
    if instructions:
        await msg.finish(I18NContext("ai.message.llm.instruct.set.success"))
    else:
        await msg.finish(I18NContext("ai.message.llm.instruct.clear.success"))


@ai.command("llm set <llm> {{I18N:ai.help.llm.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, llm: str):
    llm = llm.lower()
    if llm in llm_list:
        await msg.session_info.target_union_info.edit_target_data("ai_default_llm", llm)
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(I18NContext("ai.message.llm.invalid"))


@ai.command("llm list {{I18N:ai.help.llm.list}}")
async def _(msg: Bot.MessageSession):
    available_llms = llm_list + (llm_su_list if msg.check_super_user() else [])

    if available_llms:
        await msg.finish(
            [
                I18NContext("ai.message.llm.list"),
                Plain("\n".join(sorted(available_llms))),
                I18NContext(
                    "ai.message.llm.list.prompt",
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}ai llm set "),
                ),
            ]
        )
    else:
        await msg.finish(I18NContext("ai.message.llm.list.none"))
