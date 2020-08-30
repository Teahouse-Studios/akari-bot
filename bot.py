import asyncio
from graia.application import GraiaMiraiApplication, Session
from graia.application.event.mirai import NewFriendRequestEvent, BotInvitedJoinGroupRequestEvent
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.chain import MessageChain
from graia.broadcast import Broadcast

from MessageGen import gen

loop = asyncio.get_event_loop()

bcc = Broadcast(loop=loop, debug_flag=True)
app = GraiaMiraiApplication(
    broadcast=bcc,
    connect_info=Session(
        host="http://localhost:11919",  # 填入 httpapi 服务运行的地址
        authKey='1145141919810',  # 填入 authKey
        account=2052142661,  # 你的机器人的 qq 号
        websocket=True  # Graia 已经可以根据所配置的消息接收的方式来保证消息接收部分的正常运作.
    )
)


@bcc.receiver("GroupMessage")
async def group_message_handler(app: GraiaMiraiApplication, message: MessageChain, group: Group, member: Member):
    await gen(bcc, app, message, group, member, msgtype='group')


@bcc.receiver("FriendMessage")
async def friend_message_handler(app: GraiaMiraiApplication, message: MessageChain, friend: Friend):
    print(message)
    print('f')
    await gen(bcc, app, message, friend, msgtype='friend')


@bcc.receiver("TempMessage")
async def temp_message_handler(app: GraiaMiraiApplication, message: MessageChain, group: Group, member: Member):
    print(group.id, member.id, message.asDisplay())
    print('t')
    await gen(bcc, app, message, group, member, msgtype='temp')

@bcc.receiver("NewFriendRequestEvent")
async def NFriend(event: NewFriendRequestEvent):
    await event.accept()

@bcc.receiver("BotInvitedJoinGroupRequestEvent")
async def NGroup(event: BotInvitedJoinGroupRequestEvent):
    await event.accept()



app.launch_blocking()
