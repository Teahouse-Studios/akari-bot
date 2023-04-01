from core.component import on_regex
from core.builtins import Bot

zlp = on_regex('zhongli-probe',desc='对接钟离挂钩',developers='haoye_qwq',required_admin=True)

@zlp.handle(pattern=r'^[\s\S]*',
            mode='A',
            show_typing=False
            )
async def zl_probe(send:Bot.MessageSession):
    msg = send.matched_msg
    send_m = ['[钟离]\n'] + msg
    await Bot.FetchTarget.post_message('zhongli', send_m)
