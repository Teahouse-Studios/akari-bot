import re
import ujson as json
from core.builtins import Bot
from core.component import on_command
from core.logger import Logger
from core.utils.http import post_url
from core.utils.text import remove_suffix

s = on_command('summary', developers=['Dianliang233', 'OasisAkari'], desc='使用 InstructGPT 生成合并转发信息的聊天记录摘要。', available_for=['QQ', 'QQ|Group'])


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
    output = ''
    while nth < len(texts):
        prompt = f'请总结<|chat_start|>与<|chat_end|>之间的聊天内容。要求语言简练，但必须含有所有要点，以一段话的形式输出。' \
                 f'{f"<|ctx_start|>与<|ctx_end|>之间记录了聊天内容的上下文，你可以作为参考，但请你务必在输出结果之前将其原样复制。<|ctx_start|>{output}<|ctx_end|>" if nth != 0 else ""}'
        len_prompt = len(prompt)
        post_texts = ''
        for t in texts[nth:]:
            if len(post_texts) + len_prompt < 1970:
                post_texts += texts[nth]
                nth += 1
            else:
                break
        output += remove_suffix(await post_url('https://chat-simplifier.imzbb.cc/api/generate', data=json.dumps(
            {'prompt': f'''{prompt}<|chat_start|>
{post_texts}
<|chat_end|>'''}), headers={'Content-Type': 'application/json'}, status_code=200, timeout=9999999), '<|im_end|>')
    await wait_msg.delete()
    await msg.finish(output, disable_secret_check=True)
