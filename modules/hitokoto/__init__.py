from core.builtins import Bot
from core.component import module
from aiohttp import ClientSession
import asyncio
import orjson as json


async def hitokoto_():
    url = 'https://v1.hitokoto.cn/'
    async with ClientSession() as session:
        async with session.get(url) as response_:
            result = json.loads(await response_.text())
            if response_.status == 200:
                text = result['hitokoto']
                frm = result['from']
                who = result['from_who']
                if not who:
                    who = ''
                return f"「{text}」\n    ——{who}《{frm}》"
            else:
                return '请求失败'


hitokoto = module('hitokoto', alias=['hitk', 'saying', '一言'],
                  desc='一言', developers=['haoye_qwq'])


@hitokoto.handle('{一言}')
async def hitokoto__(msg: Bot.MessageSession):
    await msg.sendMessage(await hitokoto_())

if __name__ == '__main__':
    hit = asyncio.run(hitokoto_())
    print(hit)
