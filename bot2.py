import asyncio
from graia.application.message.elements.internal import Plain,At,Image,UploadMethods,Quote
from graia.application import GraiaMiraiApplication, Session
from graia.application.message.chain import MessageChain
from graia.application.group import Group,Member
from graia.application.friend import Friend
from graia.application.event.messages import TempMessage
from graia.broadcast import Broadcast
from os.path import abspath
from MessageGen import gen,geng,gent
loop = asyncio.get_event_loop()

bcc = Broadcast(loop=loop,debug_flag=True)
app = GraiaMiraiApplication(
    broadcast=bcc,
    connect_info=Session(
        host="http://localhost:11451", # 填入 httpapi 服务运行的地址
        authKey=41919810, # 填入 authKey
        account=2926887640, # 你的机器人的 qq 号
        websocket=True # Graia 已经可以根据所配置的消息接收的方式来保证消息接收部分的正常运作.
    )
)

@bcc.receiver("GroupMessage")
async def group_message_handler(app: GraiaMiraiApplication, message: MessageChain, group: Group, member:Member):
    print(message)
    await geng(app,message,group,member)
@bcc.receiver("FriendMessage")
async def friend_message_handler(app: GraiaMiraiApplication, message: MessageChain, friend:Friend):
    print(message)
    await gen(app,message,friend)
@bcc.receiver("TempMessage")
async def temp_message_handler(app: GraiaMiraiApplication, message: MessageChain, group: Group, member: Member):
    print(group.id, member.id, message.asDisplay())
    await gent(app,message,group,member)
app.launch_blocking()