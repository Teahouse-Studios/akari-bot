from typing import Dict, List, Tuple

import tiktoken
from openai import OpenAI, AsyncOpenAI

from core.builtins import Bot
from core.config import Config
from core.constants.exceptions import ConfigValueError, NoReportException
from core.dirty_check import check
from core.logger import Logger
from ..formatting import INSTRUCTIONS, parse_markdown

api_key = Config("ai_openai_api_key", secret=True, cfg_type=str)
if api_key:
    client = AsyncOpenAI(api_key=api_key)
    sync_client = OpenAI(api_key=api_key)

    assistant = sync_client.beta.assistants.create(
        name="AkariBot",
        instructions=INSTRUCTIONS,
        tools=[{"type": "code_interpreter"}],
        model="gpt-3.5-turbo-1106",
    )
else:
    client = None
    assistant = None

enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
INSTRUCTIONS_LENGTH = len(enc.encode(INSTRUCTIONS))
SPECIAL_TOKEN_LENGTH = 109


def count_chatgpt_token(text: str) -> int:
    return len(enc.encode(text, allowed_special="all")) + SPECIAL_TOKEN_LENGTH + INSTRUCTIONS_LENGTH


async def ask_chatgpt(msg: Bot.MessageSession, question: str) -> Tuple[List[Dict[str, str]], int]:
    if not (client and assistant):
        raise ConfigValueError(msg.locale.t("error.config.secret.not_found"))

    thread = await client.beta.threads.create(messages=[{"role": "user", "content": question}])
    run = await client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant.id)

    while True:
        run = await client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status == "completed":
            break
        if run.status == "failed":
            if run.last_error.code == "rate_limit_exceeded" and "quota" not in run.last_error.message:
                Logger.warning(run.last_error.model_dump_json())
                raise NoReportException(msg.locale.t("ask.message.rate_limit_exceeded"))
            raise RuntimeError(run.last_error.model_dump_json())
        await msg.sleep(4)

    messages = await client.beta.threads.messages.list(thread_id=thread.id)
    res = messages.data[0].content[0].text.value
    tokens = count_chatgpt_token(res)

    res = await check(res)
    resm = ""
    for m in res:
        resm += m["content"]
    return parse_markdown(resm), tokens
