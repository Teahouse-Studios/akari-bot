import io
from datetime import datetime, timezone

from openai import AsyncOpenAI, APITimeoutError, RateLimitError
from PIL import Image as PILImage

from core.builtins.bot import Bot
from core.builtins.message.internal import ImageElement, Image, Markdown, Plain, PlainElement
from core.builtins.message.chain import MessageChain
from modules.ai.config import AiConfig
from core.constants.exceptions import ExternalException
from core.utils.dirty_check import check
from core.logger import Logger
from core.utils.func import parse_time_string
from .formatting import parse_markdown, generate_code_snippet, generate_latex, generate_md_table, format_refs
from .setting import INSTRUCTIONS
from .tools import TOOLS, tool_function_calls

max_tokens = AiConfig.llm_max_tokens
timeout = AiConfig.llm_timeout
temperature = AiConfig.llm_temperature
top_p = AiConfig.llm_top_p
frequency_penalty = AiConfig.llm_frequency_penalty
presence_penalty = AiConfig.llm_presence_penalty
max_iterations = AiConfig.llm_max_calling_iteration


async def _build_user_content(prompt: str | MessageChain) -> list[dict]:
    elements = MessageChain.assign(prompt).values if isinstance(prompt, str) else prompt.values
    content = []
    for element in elements:
        if isinstance(element, PlainElement):
            content.append({"type": "text", "text": element.text})
        elif isinstance(element, ImageElement):
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": await element.get_base64(mime=True)},
                }
            )
    return content


async def ask_llm(
    session: Bot.MessageSession,
    prompt: str | MessageChain,
    model_name: str,
    api_url: str,
    api_key: str,
    use_tools: bool = True,
    history: list[dict] | None = None,
) -> tuple[list, int, int, int, list]:
    client = AsyncOpenAI(base_url=api_url, api_key=api_key)

    tz_ = session.session_info._tz_offset
    now_tz = datetime.now(timezone(parse_time_string(tz_)))
    fmt_now = now_tz.strftime("%Y-%m-%d %H:%M:%S %A") + f"(UTC{tz_})" if tz_ != "+0" else "(UTC)"

    system_messages = [
        {"role": "system", "content": INSTRUCTIONS},
        {"role": "system", "content": f"Current datetime: {fmt_now}"},
        {
            "role": "system",
            "content": f"Session language: {session.session_info.locale.t('language')}. "
            "Use this language for output unless specified by user.",
        },
    ]
    custom_instructions = session.session_info.sender_union_info.sender_data.get("ai_custom_instructions")
    if custom_instructions:
        system_messages.append({"role": "system", "content": custom_instructions})

    # 延续上下文时，历史对话（不含 system 消息）会被拼接到本次请求之前。
    conversation = list(history) if history else []
    conversation.append(
        {
            "role": "user",
            "content": await _build_user_content(prompt),
        }
    )
    messages = [*system_messages, *conversation]

    total_input_tokens = 0
    total_cached_tokens = 0
    total_output_tokens = 0
    content_pieces = []
    tool_choice = "auto" if use_tools else "none"

    iterations = 0
    while iterations <= max_iterations:
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                tool_choice=tool_choice,
                tools=TOOLS,
                max_completion_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                timeout=timeout,
                parallel_tool_calls=True,
            )
        except (APITimeoutError, RateLimitError) as e:
            raise ExternalException(e)
        except Exception as e:
            raise e

        res_msg = response.choices[0].message
        cached_tokens = response.usage.prompt_tokens_details.cached_tokens
        total_input_tokens += response.usage.prompt_tokens - cached_tokens
        total_cached_tokens += cached_tokens
        total_output_tokens += response.usage.completion_tokens

        messages.append(res_msg)
        if res_msg.content:
            content_pieces.append(res_msg.content)

        if res_msg.tool_calls:
            iterations += 1
            messages = await tool_function_calls(res_msg.tool_calls, messages)
            if iterations == max_iterations:
                Logger.warning("LLM tool calling reached maximum iterations.")
                messages.append(
                    {
                        "role": "system",
                        "content": "Warning: Iteration limit reached. Provide the final answer based on the available information and do not attempt to call tools again.",
                    }
                )
                tool_choice = "none"
            continue
        else:
            break

    res = await check("\n\n".join(content_pieces), session=session)
    resm = "".join(m["content"] for m in res)
    resm = format_refs(session, resm)

    if session.session_info.support_markdown and session.session_info.support_markdown_extension:
        chain = [Markdown(resm)]
    elif session.session_info.support_image:
        blocks = parse_markdown(resm)
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
                    chain.append(Plain(content))
            elif block["type"] == "code":
                content = block["content"]["code"]
                try:
                    content = await generate_code_snippet(content, block["content"]["language"])
                    img = PILImage.open(io.BytesIO(content))
                    chain.append(Image(img))
                except Exception:
                    chain.append(Plain(content))
            elif block["type"] == "table":
                content = block["content"]
                try:
                    path_lst = await generate_md_table(content)
                    for path in path_lst:
                        chain.append(Image(path))
                except Exception:
                    chain.append(Plain(content))
    else:
        chain = [Plain(resm)]

    # 仅保留对话部分（去掉每次动态重建的 system 消息与工具迭代警告）作为新的上下文历史。
    new_history = [m for m in messages[len(system_messages) :] if m.get("role") != "system"]
    return chain, total_input_tokens, total_cached_tokens, total_output_tokens, new_history
