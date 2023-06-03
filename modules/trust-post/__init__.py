from core.builtins import Bot
from core.component import on_command
import ujson as json

tp = on_command('trust-post', desc='向可信好友推送消息', alias='tp', required_superuser=True)


@tp.handle('<message> {?}')
async def _(msg: Bot.MessageSession):
    if msg.target.senderId == 'QQ|2031611695':
        for i in json.load(open('./modules/trust-post/trust.json')):
            f = await Bot.FetchTarget.fetch_target(i)
            await f.sendDirectMessage(msg.parsed_msg['<message>'])
    else:
        msg.sendMessage('用户非好耶，拒绝执行')
