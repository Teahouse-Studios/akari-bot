import re
from core.builtins import Bot
from core.component import on_command
from core.logger import Logger

s = on_command('summary', developers=['Dianliang233'], desc='生成聊天记录摘要', available_for=['QQ|Group'], required_superuser=True)


@s.handle()
async def _(msg: Bot.MessageSession):
    f_msg = await msg.waitNextMessage('请发送要生成摘要的合并转发消息。')
    f = re.search(r'\[Ke:forward,id=(.*?)\]', f_msg.asDisplay()).group(1)
    Logger.info(f)
    data = await f_msg.call_api('get_forward_msg', message_id=f)
    msgs = data['messages']
    text = ''
    for m in msgs:
        text += f'\n{m["sender"]["nickname"]}（ID：{m["sender"]["user_id"]}，Unix时间：{m["time"]}）：{m["content"]}'
    await msg.finish(text, disable_secret_check=True)
