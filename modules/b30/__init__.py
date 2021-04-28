from graia.application import Group, MessageChain, Friend

from .getb30 import getb30
import re
from graia.application.message.elements.internal import Image, UploadMethods, Plain
from core.template import sendMessage

async def main(kwargs: dict):
    message = kwargs['trigger_msg']
    message = message.split(' ')
    if len(message) > 1:
        msg = await getb30(message[1])
    else:
        msg = {'text': '请输入好友码！~b30 <friendcode>'}

    if 'file' in msg:
        imgchain = MessageChain.create([Image.fromLocalFile(msg['file'])])
    else:
        imgchain = False
    msgchain = MessageChain.create([Plain(msg['text'])])
    if imgchain:
        msgchain = msgchain.plusWith(imgchain)
    await sendMessage(kwargs, msgchain)


command = {'b30': main}
help = {'b30': {'module': '查询Arcaea B30结果。', 'help': '~b30 <usercode> - 查询Arcaea B30结果。'}}