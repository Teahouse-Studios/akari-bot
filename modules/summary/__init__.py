import re

import openai

from config import Config
from core.builtins import Bot
from core.component import module
from core.dirty_check import check_bool, rickroll
from core.logger import Logger

openai.api_key = Config('openai_api_key')

s = module(
    'summary',
    developers=[
        'Dianliang233',
        'OasisAkari'],
    desc='{summary.help.desc}',
    available_for=[
        'QQ',
        'QQ|Group'])


@s.handle('{{summary.help}}')
async def _(msg: Bot.MessageSession):
    f_msg = await msg.wait_next_message(msg.locale.t('summary.message'), append_instruction=False)
    try:
        f = re.search(r'\[Ke:forward,id=(.*?)\]', f_msg.as_display()).group(1)
    except AttributeError:
        await msg.finish(msg.locale.t('summary.message.not_found'))
    Logger.info(f)
    data = await f_msg.call_api('get_forward_msg', message_id=f)
    msgs = data['messages']
    texts = [f'\n{m["sender"]["nickname"]}：{m["content"]}' for m in msgs]

    char_count = sum([len(i) for i in texts])
    wait_msg = await msg.send_message(
        msg.locale.t('summary.message.waiting', count=char_count, time=round(char_count / 33.5, 1)))

    nth = 0
    prev = ''
    while nth < len(texts):
        prompt = f'请总结下列聊天内容。要求语言简练，但必须含有所有要点，以一段话的形式输出。请使用{msg.locale.locale}输出结果。除了聊天记录的摘要以外，不要输出其他任何内容。' \
                 f'''{f"""同时<ctx_start>与<|ctx_end|>之间记录了聊天内容的上下文，请你同时结合这段上下文和聊天记录来输出，并使用这段聊天记录的原语言。

<|ctx_start|>{prev}<|ctx_end|>""" if nth != 0 else ""}'''
        len_prompt = len(prompt)
        post_texts = ''
        for t in texts[nth:]:
            if len(post_texts) + len_prompt < 1970:
                post_texts += texts[nth]
                nth += 1
            else:
                break
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[
            {'role': 'system', "content": "You are a helpful assistants who summarizes chat logs."},
            {'role': 'user', "content": f'''{prompt}

{post_texts}'''},
        ]
    )
    output = completion['choices'][0]['message']['content']
    await wait_msg.delete()
    if await check_bool(output):
        rickroll(msg)
    await msg.finish(output, disable_secret_check=True)
