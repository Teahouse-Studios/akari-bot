from math import inf
import re
import ujson as json
from core.builtins import Bot
from core.component import on_command
from core.logger import Logger
from core.utils.http import post_url

s = on_command('summary', developers=['Dianliang233'], desc='生成聊天记录摘要', available_for=['QQ', 'QQ|Group'])


@s.handle()
async def _(msg: Bot.MessageSession):
    f_msg = await msg.waitNextMessage('接下来，请发送要生成摘要的合并转发消息。', append_instruction=False)
    f = re.search(r'\[Ke:forward,id=(.*?)\]', f_msg.asDisplay()).group(1)
    if not f:
        await msg.finish('未检测到合并转发消息。')
        return
    Logger.info(f)
    data = await f_msg.call_api('get_forward_msg', message_id=f)
    msgs = data['messages']
    text = ['']
    for m in msgs:
        new_text = f'\n{m["sender"]["nickname"]}：{m["content"]}'
        if (len(text[-1]) + len(new_text)) < 2000:
            text[-1] += new_text
        else:
            text.append(new_text)
    char_count = sum([len(i) for i in text])
    wait_msg = await msg.sendMessage(f'正在生成摘要。您的聊天记录共 {char_count} 个字符，大约需要 {round(len(text) / 33.5, 1)} 秒。请稍候……')

    nth = 0
    output = ''
    while nth < len(text):
        prompt = f'请总结<|chat_start|>与<|chat_end|>之间的聊天内容。要求简明扼要，以一段话的形式输出。{f"<|ctx_start|>与<|ctx_end|>之间记录了聊天内容的上下文，你可以作为参考，但请你务必在输出结果之前将其原样复制。<|ctx_start|>{output}<|ctx_end|>" if nth != 0 else ""}'
        output += (await post_url('https://chat-simplifier.imzbb.cc/api/generate', data=json.dumps(
            {'prompt': f'''{prompt}<|start|>
{text}
<|end|>'''}), headers={'Content-Type': 'application/json'}, timeout=9999999)).removesuffix('<|im_end|>')
        nth += 1
    await wait_msg.delete()
    await msg.finish(output, disable_secret_check=True)
