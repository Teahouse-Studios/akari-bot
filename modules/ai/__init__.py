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


def _get_message_images(msg: Bot.MessageSession) -> list[ImageElement]:
    messages = msg.session_info.messages
    return [element for element in messages.values if isinstance(element, ImageElement)] if messages else []


@ai.command(
    options_desc={
        "--ctx": "{I18N:ai.help.option.ctx}",
        "--llm": "{I18N:ai.help.option.llm}",
        "--no-tools": "{I18N:ai.help.option.no_tools}",
    }
)
@ai.command(
    "[<prompt>] [--ctx <turn_id>] [--llm <llm>] [--no-tools] {{I18N:ai.help}}",
    options_desc={
        "--ctx": "{I18N:ai.help.option.ctx}",
        "--llm": "{I18N:ai.help.option.llm}",
        "--no-tools": "{I18N:ai.help.option.no_tools}",
    },
)
async def _(msg: Bot.MessageSession, prompt: str = ""):
    parsed_msg = msg.parsed_msg or {}
    get_ctx = parsed_msg.get("--ctx", False)
    turn_id = get_ctx["<turn_id>"].strip() if get_ctx else None
    get_llm = parsed_msg.get("--llm", False)
    selected_llm = get_llm["<llm>"].lower() if get_llm else None
    target_default_llm = msg.session_info.target_union_info.target_data.get("ai_default_llm")
    use_tools = not parsed_msg.get("--no-tools", False)

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
    current_prompt = prompt or ""

    while True:
        images = _get_message_images(current_msg)
        if not current_prompt and not images:
            current_msg = await current_msg.wait_next_message(message_chain=I18NContext("ai.message.no_prompt"))
            current_prompt = current_msg.as_display(text_only=True).strip()
            continue

        current_is_superuser = current_msg.check_super_user()

        billing = get_llm_billing(llm_info)
        if not current_is_superuser and not precount_petal(
            current_msg,
            billing["input_price"],
            billing["output_price"],
            billing["cache_read_price"],
            billing["cache_write_price"],
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

        prompt_elements = [Plain(current_prompt)] if current_prompt else []
        prompt_chain = MessageChain.assign([*prompt_elements, *images])
        chain, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, history = await ask_llm(
            current_msg,
            prompt_chain,
            llm_info["model_name"],
            llm_info["api_url"],
            llm_info["api_key"],
            endpoint=llm_info.get("endpoint", "openai"),
            use_tools=use_tools,
            history=history,
        )

        # 每轮建立新的快照，保留旧 ID 以支持从任意一轮分叉。
        turn_id = create_context(history, context_key)

        Logger.info(
            f"{input_tokens + cache_read_tokens + cache_write_tokens + output_tokens} token used while calling LLM."
        )
        Logger.info(
            f"Input (miss cache): {input_tokens} | Output: {output_tokens} | "
            f"Cache read: {cache_read_tokens} | Cache write: {cache_write_tokens}"
        )
        billing = get_llm_billing(llm_info, input_tokens)
        petal = await count_token_petal(
            current_msg,
            billing["input_price"],
            billing["output_price"],
            billing["cache_read_price"],
            billing["cache_write_price"],
            input_tokens,
            output_tokens,
            cache_read_tokens,
            cache_write_tokens,
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
        if not current_prompt and not _get_message_images(reply):
            await msg.finish()


def _build_llm_billing_items(llm_info: dict) -> list:
    """Build the billing message items for a single LLM (used by ``llm list --price`` and ``llm price``)."""
    items = []
    billing_config = llm_info.get("billing") if isinstance(llm_info.get("billing"), dict) else {}
    billing_type = billing_config.get("type", "token")
    billing = get_llm_billing(llm_info)
    if billing_type != "per_call" and any(billing[price_name] > 0 for price_name in ("input_price", "output_price")):
        items.append(
            I18NContext(
                "ai.message.llm.list.billing.token",
                input_price=billing["input_price"],
                output_price=billing["output_price"],
            )
        )
    if billing_type != "per_call" and any(
        billing[price_name] > 0 for price_name in ("cache_write_price", "cache_read_price")
    ):
        items.append(
            I18NContext(
                "ai.message.llm.list.billing.token.cache",
                cache_write_price=billing["cache_write_price"],
                cache_read_price=billing["cache_read_price"],
            )
        )

    if billing["call_price"] > 0:
        items.append(I18NContext("ai.message.llm.list.billing.call", call_price=billing["call_price"]))

    tiers = billing_config.get("tiers")
    time_rules = billing_config.get("time_rules")
    valid_tiers = [
        tier
        for tier in tiers or []
        if isinstance(tier, dict) and isinstance(tier.get("context_threshold"), int) and tier["context_threshold"] >= 0
    ]
    if (
        billing_type != "per_call"
        and isinstance(tiers, list)
        and tiers
        and len(valid_tiers) == len(tiers)
        and not (isinstance(time_rules, list) and time_rules)
    ):
        for tier in sorted(
            valid_tiers,
            key=lambda tier: tier["context_threshold"],
        ):
            tier_billing = get_llm_billing(llm_info, tier["context_threshold"])
            if not any(
                tier_billing[price_name] > 0
                for price_name in ("input_price", "cache_write_price", "cache_read_price", "output_price")
            ):
                continue
            items.extend(
                [
                    I18NContext(
                        "ai.message.llm.list.billing.tiers.threshold",
                        context_threshold=tier["context_threshold"],
                    ),
                    I18NContext(
                        "ai.message.llm.list.billing.token",
                        input_price=tier_billing["input_price"],
                        output_price=tier_billing["output_price"],
                    ),
                    I18NContext(
                        "ai.message.llm.list.billing.token.cache",
                        cache_write_price=tier_billing["cache_write_price"],
                        cache_read_price=tier_billing["cache_read_price"],
                    ),
                ]
            )
    return items


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


@ai.command("llm price <llm> {{I18N:ai.help.llm.price}}")
async def _(msg: Bot.MessageSession, llm: str):
    llm = llm.lower()
    available_llms = llm_list + (llm_su_list if msg.check_super_user() else [])
    llm_info = next((item for item in llm_api_list if item["name"].lower() == llm), None)
    if llm_info and llm in available_llms:
        await msg.finish(
            [
                I18NContext("ai.message.llm.price", name=llm_info["name"]),
                *_build_llm_billing_items(llm_info),
            ]
        )
    else:
        await msg.finish(I18NContext("ai.message.llm.invalid"))


@ai.command(
    "llm list [--price] {{I18N:ai.help.llm.list}}", options_desc={"--price": "{I18N:ai.help.llm.list.option.price}"}
)
async def _(msg: Bot.MessageSession):
    available_llms = llm_list + (llm_su_list if msg.check_super_user() else [])
    show_price = bool(msg.parsed_msg.get("--price", False))

    if available_llms:
        llm_items = []
        for _, llm_name in enumerate(sorted(available_llms)):
            llm_info = next(llm for llm in llm_api_list if llm["name"].lower() == llm_name)
            llm_items.append(Plain(llm_name))
            if show_price:
                llm_items.extend(_build_llm_billing_items(llm_info))

        await msg.finish(
            [
                I18NContext("ai.message.llm.list"),
                *llm_items,
                I18NContext(
                    "ai.message.llm.list.prompt",
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}ai llm set "),
                ),
            ]
        )
    else:
        await msg.finish(I18NContext("ai.message.llm.list.none"))
