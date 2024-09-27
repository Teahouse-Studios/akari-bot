from core.builtins import Bot
from core.component import module
from aiohttp import ClientSession as Session
import asyncio
import ujson as json


async def hitokoto_():
    url = 'https://v1.hitokoto.cn/'
    async with Session() as session:
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
#
#
# @hitokoto.handle('cowsay {哲学牛牛}')
# async def cowsay(msg: Bot.MessageSession):
#     await msg.sendMessage(cowsay_())
#
#
# # @hitokoto.handle('echo_cave add <sth> {添加回声洞}',
# #              'echo_cave del <num> {删除回声洞}',
# #              'echo_cave {显示回声洞}')
# # async def ___(msg: Bot.MessageSession):
# #     if 'add' in msg.parsed_msg:
# #
# # cq = await msg.asDisplay()
# # cq = re.findall(r'^\[CQ:image,(\s\S)*\]', cq, re.I | re.M)
#
#
# @hitokoto.handle('{回声洞(WIP)}')
# async def ___(msg: Bot.MessageSession):
#     mode = ['hitokoto', 'cowsay']
#     if random.choice(mode) == 'hitokoto':
#         await msg.sendMessage(hitokoto_())
#     else:
#         await msg.sendMessage(cowsay_())

if __name__ == '__main__':
    hit = asyncio.run(hitokoto_())
    print(hit)
