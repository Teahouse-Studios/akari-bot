from graia.application.message.elements.internal import Plain,At,Image,UploadMethods,Quote
from graia.application import GraiaMiraiApplication, Session
from graia.application.message.chain import MessageChain
from graia.application.event.messages import TempMessage
from os.path import abspath
from CommandGen import command
import re
async def gen(app, message, friend):
    run = await command(message.asDisplay())
    print(run)
    if run != None:
        if run.find('[[usn:') != -1:
            user = re.sub(r'.*\[\[usn:|\]\]','',run)
            msg = re.sub(r'\[\[.*\]\]','',run)
            await app.sendFriendMessage(friend,MessageChain.create(\
                [Plain(msg),\
                Image.fromLocalFile(filepath=abspath(f"./assests/usercard/{user}.png"),method=UploadMethods.Friend)]).asSendable())
        else:
            await app.sendFriendMessage(friend,MessageChain.create(\
                [Plain(run)]).asSendable())
async def geng(app, message, group, member):
    run = await command(message.asDisplay(),group.id)
    print(run)
    if run != None:
        if run.find('[[usn:') != -1:
            user = re.sub(r'.*\[\[usn:|\]\]','',run)
            msg = re.sub(r'\[\[.*\]\]','',run)
            await app.sendGroupMessage(group,MessageChain.create(\
                [Plain(msg),\
                Image.fromLocalFile(filepath=abspath(f"./assests/usercard/{user}.png"),method=UploadMethods.Group)]).asSendable(),quote=message.__root__[0].id)
        else:
            await app.sendGroupMessage(group,MessageChain.create(\
                [Plain(run)]).asSendable(),quote=message.__root__[0].id)
async def gent(app, message, group, member):
    run = await command(message.asDisplay())
    print(run)
    if run != None:
        if run.find('[[usn:') != -1:
            user = re.sub(r'.*\[\[usn:|\]\]','',run)
            msg = re.sub(r'\[\[.*\]\]','',run)
            await app.sendTempMessage(group=group,target=member,message=MessageChain.create(\
                [Plain(msg),\
                Image.fromLocalFile(filepath=abspath(f"./assests/usercard/{user}.png"),method=UploadMethods.Temp)]).asSendable())
        else:
            await app.sendTempMessage(group=group,target=member,message=MessageChain.create(\
                [Plain(run)]).asSendable())


"""
        await app.sendGroupMessage(group,MessageChain.create(\
                [At(member.id),Plain(msg),\
                Image.fromLocalFile(filepath=abspath("./assests/usercard/Lightyzhh.png"),method=UploadMethods.Group)]).asSendable())
"""