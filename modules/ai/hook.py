"""ai.ask 具名 hook - 供其他模块调用 AI 对话能力。"""

from attrs import define, field

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import PlainElement
from core.logger import Logger
from .petal import count_token_petal, precount_petal
from .setting import default_llm, get_llm_billing, llm_api_list, llm_list, llm_su_list

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"
STATUS_NOT_ENOUGH_PETAL = "not_enough_petal"


@define
class AiHookResult:
    """ai.ask 的调用结果。

    :param status: 调用状态，``ok`` 表示调用成功。
    :param text: 模型回答的纯文本内容。
    :param chain: 可直接发送的消息元素列表。
    :param petal: 本次调用扣除的花瓣数。
    :param llm: 实际使用的模型名称。
    """

    status: str
    text: str = ""
    chain: list = field(factory=list)
    petal: int = 0
    llm: str = ""


def resolve_llm(name: str | None, session_info) -> dict | None:
    """按调用方指定、场景默认、模块默认的顺序确定模型。

    调用方显式指定模型时不做替换；场景默认模型已下线时回落到模块默认模型。

    :param name: 调用方指定的模型名称。
    :param session_info: 调用方所在会话。
    :return: 模型配置；不可用时返回 None。
    """
    available_llms = llm_list + (llm_su_list if session_info.superuser else [])
    target_union_info = session_info.target_union_info
    target_default_llm = target_union_info.target_data.get("ai_default_llm") if target_union_info else None
    candidates = [name] if name else [target_default_llm, default_llm]
    selected_llm = next(
        (candidate.lower() for candidate in candidates if candidate and candidate.lower() in available_llms), None
    )
    if not selected_llm:
        return None
    return next((llm for llm in llm_api_list if llm["name"].lower() == selected_llm), None)


async def ask_ai(ctx: Bot.ModuleHookContext) -> AiHookResult:
    """调用模型完成一次对话，并按实际用量扣除花瓣。

    ``ctx.args`` 支持的参数：

    - ``prompt``：用户输入，字符串或 ``MessageChain``。
    - ``instructions``：追加在系统提示之后的任务说明，用于约束本次输出。
    - ``llm``：指定模型名称，缺省时依次取场景默认模型与模块默认模型。
    - ``use_tools``：是否允许工具调用，默认为关闭。

    :param ctx: 模块 hook 上下文。
    :return: 调用结果；``status`` 非 ``ok`` 时不含回答内容。
    """
    args = ctx.args
    session_info = ctx.session_info
    prompt = args.get("prompt")
    if session_info is None or not prompt:
        return AiHookResult(STATUS_UNAVAILABLE)
    if not isinstance(prompt, MessageChain):
        prompt = MessageChain.assign(prompt)

    llm_info = resolve_llm(args.get("llm"), session_info)
    if not llm_info:
        return AiHookResult(STATUS_UNAVAILABLE)

    billing = get_llm_billing(llm_info)
    if not precount_petal(
        session_info,
        billing["input_price"],
        billing["output_price"],
        billing["cache_read_price"],
        billing["cache_write_price"],
        call_price=billing["call_price"],
    ):
        return AiHookResult(STATUS_NOT_ENOUGH_PETAL, llm=llm_info["name"])

    # OpenAI、Matplotlib、网页提取等依赖体积较大，仅在实际调用 AI 时加载。
    from .llm import ask_llm

    # hook 上下文只带 SessionInfo，而模型调用与出站格式化都需要消息会话。
    session = Bot.MessageSession(session_info)
    chain, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, _history = await ask_llm(
        session,
        prompt,
        llm_info["model_name"],
        llm_info["api_url"],
        llm_info["api_key"],
        endpoint=llm_info.get("endpoint", "openai"),
        use_tools=bool(args.get("use_tools", False)),
        extra_instructions=args.get("instructions"),
    )

    Logger.info(
        f"{input_tokens + cache_read_tokens + cache_write_tokens + output_tokens} token used while calling LLM "
        "through ai.ask hook."
    )
    billing = get_llm_billing(llm_info, input_tokens)
    petal = await count_token_petal(
        session_info,
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

    return AiHookResult(
        STATUS_OK,
        text="".join(element.text for element in chain if isinstance(element, PlainElement)),
        chain=chain,
        petal=petal,
        llm=llm_info["name"],
    )


__all__ = ["AiHookResult", "STATUS_NOT_ENOUGH_PETAL", "STATUS_OK", "STATUS_UNAVAILABLE", "ask_ai", "resolve_llm"]
