from core.component import on_regex
from core.builtins import Bot
import ast
import re

zlp = on_regex('zhongli-probe', desc='对接钟离挂钩', developers='haoye_qwq', required_admin=True)


@zlp.handle(pattern=r'[\w\W]*^',
            mode='A',
            show_typing=False
            )
async def zl_probe(send: Bot.MessageSession):
    msg = send.matched_msg[0]
    string = str(re.search(r'\{(?<=\{)[^}]*(?=\})\}', msg))
    msg = ast.literal_eval(string)
    send_m = '[钟离]/n' + msg['text']
    f = await Bot.FetchTarget.fetch_target(msg['return_to'])
    await f.sendDirectMessage(send_m.replace('/n', '\n'))
