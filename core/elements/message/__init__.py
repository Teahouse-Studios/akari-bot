from core.aiohttp import aiohttp
from core.aiohttp import aiohttp_session
from config import CachePath
import uuid
import filetype
import asyncio

class MsgInfo:
    def __init__(self,
                 targetId,
                 targetName,
                 senderId,
                 senderName,
                 msgFrom
                 ):
        self.targetId = targetId
        self.targetName = targetName
        self.senderId = senderId
        self.senderName = senderName
        self.msgFrom = msgFrom


class InfoChain:
    def __init__(self,
                 target,
                 messageChain):
        self.target = target
        self.messageChain = messageChain


class Plain:
    def __init__(self,
                 text):
        self.text = text


class Image:
    def __init__(self,
                 url=None,
                 path=None):
        if url is not None:
            path = asyncio.run(self.get_image(url))
        self.image = path


    async def get_image(self, url, headers=None):
        session = await aiohttp_session(headers=headers)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
            raw = await req.read()
            ft = filetype.match(raw).extension
            img_path = f'{CachePath}{str(uuid.uuid4())}.{ft}'
            with open(img_path, 'wb+') as image_cache:
                image_cache.write(raw)
            return img_path


