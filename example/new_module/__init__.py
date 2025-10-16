import re

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image
from core.component import module
from core.scheduler import IntervalTrigger

test = module("test")


@test.command()
async def _(msg: Bot.MessageSession):
    #  >>> ~test
    #  <<< Hello World!
    await msg.send_message("Hello World!")


@test.command("say <word>")
async def _(msg: Bot.MessageSession, word: str):
    #  >>> ~test say Word
    #  <<< Word is Word
    await msg.finish(f"{word} is {msg.parsed_msg["<word>"]}")


@test.command("reply")
async def _(msg: Bot.MessageSession):
    #  >>> ~test reply
    #  <<< Reply me!
    #  >>> Hello World! >> [Reply me!]
    #  <<< Hello World!
    s = await msg.wait_reply("Reply me!")
    await s.send_message(s.as_display())


@test.command("confirm")
async def _(msg: Bot.MessageSession):
    #  >>> ~test confirm
    #  <<< Are you sure?
    #  >>> Yes
    #  <<< OK!
    if await msg.wait_confirm("Are you sure?"):
        await msg.send_message("OK!")


@test.command("msgchain")
async def _(msg: Bot.MessageSession):
    #  >>> ~test msgchain
    #  <<< A picture: Image(url="https://http.cat/100.jpg")
    #  <<< KE Code is also Image(url="https://http.cat/200.jpg")
    await msg.send_message(MessageChain.assign([Plain("A picture:"), Image("https://http.cat/100.jpg")]))
    await msg.send_message("[KE:plain,text=KE Code is also][KE:image,path=https://http.cat/200.jpg][KE:i18n,i18nkey=example]")


@test.regex(r"\{\{(.*?)}}", mode="M")  # re.match
async def _(msg: Bot.MessageSession):
    #  >>> {{Hello World!}}
    #  <<< Hello World!
    await msg.finish(msg.matched_msg.group(1))


@test.regex(r"\[\[(.*?)]]", mode="A")  # re.findall
async def _(msg: Bot.MessageSession):
    #  >>> [[Hello]] [[World]]
    #  <<< Hello
    #  <<< World
    for x in msg.matched_msg:
        await msg.send_message(x)


@test.schedule(IntervalTrigger(seconds=30))
async def _():
    # Send a message to target which is enabled test module every 30 seconds
    await Bot.post_message("test", "This message is sent per 30 seconds")


@test.handle("test")  # all in one handler, including command, regex and schedule
async def _(msg: Bot.MessageSession):
    #  >>> ~test test
    #  <<< Hello World!
    await msg.finish("Hello World Again!")


@test.handle(re.compile(r"<(.*?)>"), mode="A")  # re.findall
async def _(msg: Bot.MessageSession):
    #  >>> <Hello World!>
    #  <<< Hello World!
    await msg.finish(msg.matched_msg[0])


@test.handle(IntervalTrigger(seconds=60))
async def _():
    # Send a message to target which is enabled test module every 60 seconds
    await Bot.post_message("test", "This message is sent per 60 seconds")
