import re

from core.builtins import Plain, Image, Bot
from core.component import module
from core.scheduler import IntervalTrigger

test = module('test')


@test.command()
async def _(session: Bot.MessageSession):
    #  >>> ~test
    #  <<< Hello World!
    await session.send_message('Hello World!')


@test.command('say <word>')
async def _(session: Bot.MessageSession):
    #  >>> ~test say Hello World!
    #  <<< Hello World!
    await session.finish(session.parsed_msg['<word>'])


@test.command('reply')
async def _(session: Bot.MessageSession):
    #  >>> ~test reply
    #  <<< Reply me!
    #  >>> Hello World! >> [Reply me!]
    #  <<< Hello World!
    s = await session.wait_reply('Send a word')
    await s.send_message(s.as_display())


@test.command('confirm')
async def _(session: Bot.MessageSession):
    #  >>> ~test confirm
    #  <<< Are you sure?
    #  >>> Yes
    #  <<< OK!
    s = await session.wait_confirm('Are you sure?')
    if s:
        await s.send_message('OK!')


@test.command('image')
async def _(session: Bot.MessageSession):
    #  >>> ~test image
    #  <<< A picture: Image(url='https://http.cat/100.jpg')
    await session.send_message([Plain('A picture:'), Image('https://http.cat/100.jpg')])


@test.regex(re.compile(r'\{\{(.*)}}'), mode='M')  # re.match
async def _(session: Bot.MessageSession):
    #  >>> {{Hello World!}}
    #  <<< Hello World!
    await session.finish(session.matched_msg.group(1))


@test.regex(re.compile(r'\[\[(.*)]]'), mode='A')  # re.findall
async def _(session: Bot.MessageSession):
    #  >>> [[Hello]] [[World]]
    #  <<< Hello
    #  <<< World
    await session.send_message(session.matched_msg[0])
    await session.finish(session.matched_msg[1])


@test.schedule(IntervalTrigger(seconds=30))
async def _():
    # Send a message to target which is enabled test module every 30 seconds
    await Bot.FetchTarget.post_message('test', 'Hello World!')


@test.handle('test')  # all in one handler, including command, regex and schedule
async def _(session: Bot.MessageSession):
    #  >>> ~test test
    #  <<< Hello World!
    await session.finish('Hello World!')


@test.handle(re.compile(r'<(.*)>'), mode='A')  # re.findall
async def _(session: Bot.MessageSession):
    #  >>> <Hello World!>
    #  <<< Hello World!
    await session.finish(session.matched_msg[0])


@test.handle(IntervalTrigger(seconds=60))
async def _():
    # Send a message to target which is enabled test module every 60 seconds
    await Bot.FetchTarget.post_message('test', 'test')
