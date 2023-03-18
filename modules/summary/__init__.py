import re
import openai

from core.builtins import Bot
from core.component import module
from core.logger import Logger
from config import Config

openai.api_key = Config('openai_api_key')

s = module('summary', developers=['Dianliang233', 'OasisAkari'], desc='使用 InstructGPT 生成合并转发信息的聊天记录摘要。', available_for=['QQ', 'QQ|Group'])


@s.handle('{开始发送聊天摘要}')
async def _(msg: Bot.MessageSession):
    f_msg = await msg.waitNextMessage('接下来，请发送要生成摘要的合并转发消息。', append_instruction=False)
    try:
        f = re.search(r'\[Ke:forward,id=(.*?)\]', f_msg.asDisplay()).group(1)
    except AttributeError:
        await msg.finish('未检测到合并转发消息。')
    Logger.info(f)
    data = await f_msg.call_api('get_forward_msg', message_id=f)
    msgs = data['messages']
    texts = [f'\n{m["sender"]["nickname"]}：{m["content"]}' for m in msgs]

    char_count = sum([len(i) for i in texts])
    wait_msg = await msg.sendMessage(f'正在生成摘要。您的聊天记录共 {char_count} 个字符，大约需要 {round(char_count / 33.5, 1)} 秒。请稍候……')

    nth = 0
    prev = ''
    while nth < len(texts):
        prompt = f'请总结下列聊天内容。要求语言简练，但必须含有所有要点，以一段话的形式输出。' \
                 f'''{f"""同时<ctx_start>与<|ctx_end|>之间记录了聊天内容的上下文，请你同时结合这段上下文和聊天记录来输出。

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
                    {'role': 'system', "content": "你是一个助手"},
                    {'role': 'user', "content": f'''{prompt}

{post_texts}'''},
                ]
        )
    output = completion
    await wait_msg.delete()
    await msg.finish(output, disable_secret_check=True)
