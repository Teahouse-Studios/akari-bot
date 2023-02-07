import re
import ujson as json
from core.builtins import Bot
from core.component import on_command
from core.logger import Logger
from core.utils.http import post_url

s = on_command('summary', developers=['Dianliang233'], desc='生成聊天记录摘要', available_for=['QQ|Group'])


@s.handle()
async def _(msg: Bot.MessageSession):
    f_msg = await msg.waitNextMessage('请发送要生成摘要的合并转发消息。', append_instruction=False)
    f = re.search(r'\[Ke:forward,id=(.*?)\]', f_msg.asDisplay()).group(1)
    if not f:
        await msg.finish('未检测到合并转发消息。')
        return
    Logger.info(f)
    data = await f_msg.call_api('get_forward_msg', message_id=f)
    msgs = data['messages']
    text = ''
    for m in msgs:
        text += f'\n{m["sender"]["nickname"]}（ID：{m["sender"]["user_id"]}，Unix时间：{m["time"]}）：{m["content"]}'
    wait_msg = await msg.sendMessage(f'正在生成摘要。您的聊天记录共 {len(text)} 个字符，大约需要 {round(len(text) / 33.5, 1)} 秒请稍候……')
    res = await post_url('https://chat-simplifier.imzbb.cc/api/generate', data=json.dumps({'promt': f'''把以下聊天记录概括为一段完整的纪要。当遇到!!!CHATENDS时，聊天记录结束，请在下方续写其摘要：

{text}
!!!CHATENDS'''}), headers={'Content-Type': 'application/json'})
    await wait_msg.delete()
    await msg.finish(res.removesuffix('<|im_end|>'), disable_secret_check=True)
