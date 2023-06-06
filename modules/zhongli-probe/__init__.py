from core.component import on_regex
from core.builtins import Bot
from ast import literal_eval
from re import search

zlp = on_regex('zhongli-probe', desc='对接钟离挂钩', developers='haoye_qwq', required_superuser=True)


@zlp.handle(pattern=r'^[\s\S]*',
            mode='A',
            show_typing=False
            )
async def zl_probe(send: Bot.MessageSession):
    msg = str(send.matched_msg[0])
    msg = literal_eval(str(search(r'^\{[\s\S]*', msg.replace('\n', '/n'))))
    send_m = '[钟离]/n' + msg['text']
    f = await Bot.FetchTarget.fetch_target(msg['return_to'])
    await f.sendDirectMessage(send_m.replace('/n', '\n'))
