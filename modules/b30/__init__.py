from graia.application import Group, MessageChain, Friend

from .getb30 import getb30
import re
from graia.application.message.elements.internal import Image, UploadMethods, Plain
from core.template import sendMessage

async def main(kwargs: dict):
    message = kwargs['trigger_msg']
    message = re.sub('b30 ', '', message)
    msg = await getb30(message)

    if 'file' in msg:
        if Group in kwargs:
            mth = UploadMethods.Group
        if Friend in kwargs:
            mth = UploadMethods.Friend
        imgchain = MessageChain.create([Image.fromLocalFile(msg['file'], method=mth)])
    else:
        imgchain = False
    msgchain = MessageChain.create([Plain(msg['text'])])
    if imgchain:
        msgchain = msgchain.plusWith(imgchain)
    await sendMessage(kwargs, msgchain)


command = {'b30': main}
help = {'b30': {'module': '查询Arcaea B30结果。', 'help': '~b30 <usercode> - 查询Arcaea B30结果。'}}