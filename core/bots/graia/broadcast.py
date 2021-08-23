import asyncio

from graia.application import GraiaMiraiApplication, Session
from graia.broadcast import Broadcast

from config import Config
from core.logger import Logginglogger

loop = asyncio.get_event_loop()

c = Config
debug = c('debug_flag')
bcc = Broadcast(loop=loop, debug_flag=debug)
app = GraiaMiraiApplication(
    broadcast=bcc,
    enable_chat_log=c('qq_enable_chat_log'),
    connect_info=Session(
        host=c('qq_host'),  # 填入 httpapi 服务运行的地址
        authKey=c('qq_authkey'),  # 填入 authKey
        account=c('qq_account'),  # 你的机器人的 qq 号
        websocket=c('qq_websocket')  # Graia 已经可以根据所配置的消息接收的方式来保证消息接收部分的正常运作.
    ),
    logger=Logginglogger(**({"debug": True} if debug else {}))
)
