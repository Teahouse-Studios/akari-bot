import io
import re

import tiktoken
from PIL import Image as PILImage
from openai import OpenAI, AsyncOpenAI

from core.builtins import Bot, I18NContext, Image, Plain
from core.component import module
from core.config import Config
from core.constants.exceptions import ConfigValueError, NoReportException
from core.dirty_check import check, check_bool, rickroll
from core.logger import Logger
from core.utils.cooldown import CoolDown
from .formatting import generate_latex, generate_code_snippet
from .petal import count_token_petal

if Config("openai_api_key", secret=True, cfg_type=str):
    client = AsyncOpenAI(
        api_key=Config("openai_api_key", cfg_type=str, secret=True),
    )

    sync_client = OpenAI(
        api_key=Config("openai_api_key", cfg_type=str, secret=True),
    )

    INSTRUCTIONS = """You are the chat mode of AkariBot (Chinese: 小可), a chat bot created by Teahouse Studios (Chinese: 茶馆工作室)

    Provide informative, logical, and engaging answers with details to cover multiple aspects of the question. Use emojis when appropriate for added interest.

    Use LaTeX to output math, physics or chemistry expressions whenever possible, and surround the expression with dollar signs `$`, e.g. $E=mc^2$.

    Refrain from answering any questions related to politics, geopolitics, political figures, politicians, political events or political ideologies. Decline to answer immediately and tell the user that the question is inappropriate."""

    assistant = sync_client.beta.assistants.create(
        name="AkariBot",
        instructions=INSTRUCTIONS,
        tools=[{"type": "code_interpreter"}],
        model="gpt-3.5-turbo-1106",
    )

    # assistant_gpt4 = sync_client.beta.assistants.create(
    #     name="AkariBot",
    #     instructions=INSTRUCTIONS,
    #     tools=[{"type": "code_interpreter"}],
    #     model="gpt-4-1106-preview"
    # )
else:
    INSTRUCTIONS = ""

a = module("ask", developers=["Dianliang233"], desc="{ask.help.desc}", doc=True)


@a.command("[-4] <question> {{ask.help}}")
@a.regex(
    r"^(?:question||问|問)[\:：]\s?(.+?)[?？]$", flags=re.I, desc="{ask.help.regex}"
)
async def _(msg: Bot.MessageSession):
    is_superuser = msg.check_super_user()
    if not Config("openai_api_key", cfg_type=str, secret=True):
        raise ConfigValueError(msg.locale.t("error.config.secret.not_found"))
    if Config("enable_petal", False) and not is_superuser and msg.petal <= 0:  # refuse
        await msg.finish(msg.locale.t("petal.message.cost.not_enough"))

    qc = CoolDown("call_openai", msg)
    c = qc.check(60)
    if c == 0 or msg.target.client_name == "TEST" or is_superuser:
        if hasattr(msg, "parsed_msg"):
            question = msg.parsed_msg["<question>"]
            # gpt4 = bool(msg.parsed_msg["-4"])
        else:
            question = msg.matched_msg[0]
            # gpt4 = False
        if await check_bool(question):
            await msg.finish(rickroll(msg))

        thread = await client.beta.threads.create(
            messages=[{"role": "user", "content": question}]
        )
        run = await client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id,
        )
        while True:
            run = await client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id
            )
            if run.status == "completed":
                break
            if run.status == "failed":
                if (
                    run.last_error.code == "rate_limit_exceeded"
                    and "quota" not in run.last_error.message
                ):
                    Logger.warning(run.last_error.json())
                    raise NoReportException(
                        msg.locale.t("ask.message.rate_limit_exceeded")
                    )
                raise RuntimeError(run.last_error.json())
            await msg.sleep(4)

        messages = await client.beta.threads.messages.list(thread_id=thread.id)

        res = messages.data[0].content[0].text.value
        tokens = count_token(res)

        petal = await count_token_petal(msg, tokens)
        # petal = await count_token_petal(msg, tokens, gpt4)

        res = await check(res, msg=msg)
        resm = ""
        for m in res:
            resm += m["content"]
        blocks = parse_markdown(resm)

        chain = []
        for block in blocks:
            if block["type"] == "text":
                chain.append(Plain(block["content"]))
            elif block["type"] == "latex":
                content = ""
                try:
                    content = await generate_latex(block["content"])
                    img = PILImage.open(io.BytesIO(content))
                    chain.append(Image(img))
                except Exception:
                    chain.append(
                        I18NContext("ask.message.text2img.error", text=content)
                    )
            elif block["type"] == "code":
                content = block["content"]["code"]
                try:
                    chain.append(
                        Image(
                            PILImage.open(
                                io.BytesIO(
                                    await generate_code_snippet(
                                        content, block["content"]["language"]
                                    )
                                )
                            )
                        )
                    )
                except Exception:
                    chain.append(
                        I18NContext("ask.message.text2img.error", text=content)
                    )

        if petal != 0:
            chain.append(I18NContext("petal.message.cost", amount=petal))

        if msg.target.client_name != "TEST" and not is_superuser:
            qc.reset()
        await msg.finish(chain)
    else:
        await msg.finish(msg.locale.t("message.cooldown", time=int(60 - c)))


def parse_markdown(md: str):
    regex = r"(```[\s\S]*?\n```|\\\[[\s\S]*?\\\]|[^\n]+)"

    blocks = []
    for match in re.finditer(regex, md):
        content = match.group(1)

        if content.startswith("```"):
            block = "code"
            try:
                language, code = re.match(r"```(.*)\n([\s\S]*?)\n```", content).groups()
            except AttributeError:
                raise ValueError("Code block is missing language or code.")
            content = {"language": language, "code": code}
        elif content.startswith("\\["):
            block = "latex"
            content = content[2:-2].strip()
        else:
            block = "text"
        blocks.append({"type": block, "content": content})

    return blocks


enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
INSTRUCTIONS_LENGTH = len(enc.encode(INSTRUCTIONS))
SPECIAL_TOKEN_LENGTH = 109


def count_token(text: str):
    return (
        len(enc.encode(text, allowed_special="all"))
        + SPECIAL_TOKEN_LENGTH
        + INSTRUCTIONS_LENGTH
    )
