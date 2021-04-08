import asyncio

from graia.application import GraiaMiraiApplication, Session
from graia.broadcast import Broadcast

from config import Config

loop = asyncio.get_event_loop()
c = Config

bcc = Broadcast(loop=loop, debug_flag=c('debug_flag'))
app = GraiaMiraiApplication(
    broadcast=bcc,
    enable_chat_log=c('enable_chat_log'),
    connect_info=Session(
        host=c('host'),  # 填入 httpapi 服务运行的地址
        authKey=c('authkey'),  # 填入 authKey
        account=c('account'),  # 你的机器人的 qq 号
        websocket=c('websocket')  # Graia 已经可以根据所配置的消息接收的方式来保证消息接收部分的正常运作.
    )
)
