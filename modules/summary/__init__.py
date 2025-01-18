import re

from openai import AsyncOpenAI

from core.builtins import Bot
from core.component import module
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.dirty_check import check, check_bool, rickroll
from core.logger import Logger
from core.utils.cooldown import CoolDown
from modules.ask.petal import count_token_petal

client = (
    AsyncOpenAI(
        api_key=Config("openai_api_key", cfg_type=str, secret=True),
    )
    if Config("openai_api_key", secret=True)
    else None
)

s = module(
    "summary",
    developers=["Dianliang233", "OasisAkari"],
    desc="{summary.help.desc}",
    doc=True,
    available_for=["QQ|Private", "QQ|Group"],
)


@s.command("{{summary.help}}")
async def _(msg: Bot.MessageSession):
    is_superuser = msg.check_super_user()
    if not Config("openai_api_key", cfg_type=str, secret=True):
        raise ConfigValueError(msg.locale.t("error.config.secret.not_found"))
    if Config("enable_petal", False) and not is_superuser and msg.petal <= 0:  # refuse
        await msg.finish(msg.locale.t("petal.message.cost.not_enough"))

    qc = CoolDown("call_openai", msg)
    c = qc.check(60)
    if c == 0 or msg.target.client_name == "TEST" or is_superuser:
        f_msg = await msg.wait_next_message(
            msg.locale.t("summary.message"), append_instruction=False
        )
        try:
            f = re.search(r"\[CQ:forward,id=(-?\d+).*?]", f_msg.as_display()).group(1)
            Logger.info(f)
        except AttributeError:
            await msg.finish(msg.locale.t("summary.message.not_found"))

        data = await f_msg.call_api("get_forward_msg", message_id=f)
        msgs = data["messages"]
        texts = [f'\n{m["sender"]["nickname"]}：{m["content"]}' for m in msgs]
        if await check_bool("".join(texts)):
            await msg.finish(rickroll())

        char_count = sum(len(i) for i in texts)
        wait_msg = await msg.send_message(
            msg.locale.t(
                "summary.message.waiting",
                count=char_count,
                time=round(char_count / 33.5, 1),
            )
        )

        nth = 0
        prev = ""
        while nth < len(texts):
            prompt = (
                f"请总结下列聊天内容。要求语言简练，但必须含有所有要点，以一段话的形式输出。请使用{msg.locale.locale}输出结果。除了聊天记录的摘要以外，不要输出其他任何内容。"
                f'''{f"""同时<ctx_start>与<|ctx_end|>之间记录了聊天内容的上下文，请你同时结合这段上下文和聊天记录来输出。

    <|ctx_start|>{prev}<|ctx_end|>""" if nth != 0 else ""}'''
            )
            len_prompt = len(prompt)
            post_texts = ""
            for _ in texts[nth:]:
                if len(post_texts) + len_prompt < 1970:
                    post_texts += texts[nth]
                    nth += 1
                else:
                    break
        completion = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistants who summarizes chat logs.",
                },
                {
                    "role": "user",
                    "content": f"""{prompt}

    {post_texts}""",
                },
            ],
        )
        output = completion.choices[0].message.content
        tokens = completion.usage.total_tokens

        petal = await count_token_petal(msg, tokens)
        if petal != 0:
            output = f"{output}\n{msg.locale.t('petal.message.cost', amount=petal)}"
        await wait_msg.delete()

        if msg.target.client_name != "TEST" and not is_superuser:
            qc.reset()

        output = await check(output)
        o = ""
        for m in output:
            o += m["content"]
        await msg.finish(o)
    else:
        await msg.finish(msg.locale.t("message.cooldown", time=int(c)))
