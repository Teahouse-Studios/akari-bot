import re
from core.builtins import Bot
from core.component import on_command

s = on_command('summary', developers=['Dianliang233'], desc='生成聊天记录摘要', available_for=['QQ|Group'], required_superuser=True)


@s.handle()
async def _(msg: Bot.MessageSession):
    f_msg = await msg.waitNextMessage('请发送要生成摘要的合并转发消息。')
    data = await f_msg.call_api('get_forward_msg', msg_id=re.search(r'\[CQ:forward,id=(.*?)\]', f_msg.trigger_msg).group(1))
    msgs = data['messages']
    for m in msgs:
        text += f'{m["sender"]["nickname"]}（ID：{m["sender"]["user_id"]}，Unix时间：{m["time"]}）：{m["content"]}\n'
    await msg.send(text)
