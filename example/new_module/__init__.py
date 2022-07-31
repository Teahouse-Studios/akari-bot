from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Plain, Image

test = on_command('test')


@test.handle()
async def _(session: MessageSession):
    await session.sendMessage('Hello World!')


@test.handle('say <word>')
async def _(session: MessageSession):
    await session.finish(session.parsed_msg['<word>'])


@test.handle('reply')
async def _(session: MessageSession):
    s = await session.waitReply('Send a word')
    await s.sendMessage(s.asDisplay())


@test.handle('image')
async def _(session: MessageSession):
    await session.sendMessage([Plain('A picture:'), Image('https://http.cat/100.jpg')])
