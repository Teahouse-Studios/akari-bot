from core.builtins import Plain, Image, Bot
from core.builtins.message import MessageSession
from core.component import module
from core.scheduler import IntervalTrigger

import re

test = module('test')


@test.command()
async def _(session: MessageSession):
    #  >>> ~test
    #  <<< Hello World!
    await session.sendMessage('Hello World!')


@test.command('say <word>')
async def _(session: MessageSession):
    #  >>> ~test say Hello World!
    #  <<< Hello World!
    await session.finish(session.parsed_msg['<word>'])


@test.command('reply')
async def _(session: MessageSession):
    #  >>> ~test reply
    #  <<< Send a word
    #  >>> Hello World!
    #  <<< Hello World!
    s = await session.waitReply('Send a word')
    await s.sendMessage(s.asDisplay())


@test.command('image')
async def _(session: MessageSession):
    #  >>> ~test image
    #  <<< A picture: Image(url='https://http.cat/100.jpg')
    await session.sendMessage([Plain('A picture:'), Image('https://http.cat/100.jpg')])


@test.regex(re.compile(r'\{\{(.*)}}'), mode='M')  # re.match
async def _(session: MessageSession):
    #  >>> {{Hello World!}}
    #  <<< Hello World!
    await session.finish(session.matched_msg.group(1))


@test.regex(re.compile(r'\[\[(.*)]]'), mode='A')  # re.findall
async def _(session: MessageSession):
    #  >>> [[Hello]] [[World]]
    #  <<< Hello
    #  <<< World
    await session.finish(session.matched_msg[0])
    await session.finish(session.matched_msg[1])


@test.schedule(IntervalTrigger(seconds=30))
async def _():
    # Send a message to target every 30 seconds
    await Bot.FetchTarget.post_message('test', 'Hello World!')
