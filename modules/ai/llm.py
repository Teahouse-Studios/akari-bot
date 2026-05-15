import io
from datetime import datetime, timezone

from openai import AsyncOpenAI, APITimeoutError, RateLimitError
from PIL import Image as PILImage

from core.builtins.bot import Bot
from core.builtins.message.internal import Image, Plain
from core.config import Config
from core.constants.exceptions import ExternalException
from core.dirty_check import check
from core.logger import Logger
from core.utils.func import parse_time_string
from .formatting import parse_markdown, generate_code_snippet, generate_latex, generate_md_table
from .setting import INSTRUCTIONS
from .tools import TOOLS, tool_function_calls

max_tokens = Config("llm_max_tokens", 2048, table_name="module_ai")
timeout = Config("llm_timeout", 60, cfg_type=float, table_name="module_ai")
temperature = Config("llm_temperature", 1, cfg_type=float, table_name="module_ai")
top_p = Config("llm_top_p", 1, cfg_type=float, table_name="module_ai")
frequency_penalty = Config("llm_frequency_penalty", 0, cfg_type=float, table_name="module_ai")
presence_penalty = Config("llm_presence_penalty", 0, cfg_type=float, table_name="module_ai")

MAX_ITERATIONS = 6


async def ask_llm(
    session: Bot.MessageSession,
    prompt: str,
    model_name: str,
    api_url: str,
    api_key: str,
    use_tools: bool = True,
) -> tuple[list, int, int]:
    client = AsyncOpenAI(base_url=api_url, api_key=api_key)

    tz_ = session.session_info.target_info.target_data.get("timezone_offset", Config("timezone_offset", "+8"))
    now_tz = datetime.now(timezone(parse_time_string(tz_)))
    fmt_now = now_tz.strftime("%Y-%m-%d %H:%M:%S %A") + f"(UTC{tz_})" if tz_ != "+0" else "(UTC)"

    messages = [
        {"role": "system", "content": INSTRUCTIONS},
        {"role": "system", "content": f"Current datetime: {fmt_now}"},
        {"role": "user", "content": prompt},
    ]
    custom_instructions = session.session_info.sender_info.sender_data.get("ai_custom_instructions")
    if custom_instructions:
        messages.insert(2, {"role": "system", "content": custom_instructions})

    total_input_tokens = 0
    total_output_tokens = 0
    content_pieces = []
    tool_choice = "auto" if use_tools else "none"

    iterations = 0
    while iterations <= MAX_ITERATIONS:
        is_final_attempt = iterations == MAX_ITERATIONS
        if is_final_attempt:
            messages.append(
                {
                    "role": "system",
                    "content": "Warning: Iteration limit reached. Provide the final answer based on the available information and do not attempt to call functions again.",
                }
            )
            tool_choice = "none"
        try:
            completion = await client.chat.completions.create(
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
            )
        except (APITimeoutError, RateLimitError) as e:
            raise ExternalException(e)
        except Exception as e:
            raise e

        res_msg = completion.choices[0].message
        total_input_tokens += completion.usage.prompt_tokens
        total_output_tokens += completion.usage.completion_tokens

        messages.append(res_msg)
        if res_msg.content:
            content_pieces.append(res_msg.content)
        if res_msg.tool_calls and not is_final_attempt:
            messages = await tool_function_calls(res_msg.tool_calls, messages)
            iterations += 1
            continue
        else:
            break
    else:
        Logger.warning("LLM function calling reached maximum iterations.")

    res = await check("\n\n".join(content_pieces), session=session)
    resm = "".join(m["content"] for m in res)

    if session.session_info.support_image:
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

    return chain, total_input_tokens, total_output_tokens
