from core.component import module
from core.builtins import Bot
import hashlib

hsh = module('hash', desc='生成对应字符串的哈希值', developers='haoye_qwq')


@hsh.handle('<algorithm> <string>')
async def _(msg: Bot.MessageSession):
    try:
        hash_ = hashlib.new(msg.parsed_msg['<algorithm>'], msg.parsed_msg['<string>'].encode('utf-8'))
        await msg.sendMessage(f"该字符串的 {msg.parsed_msg['<algorithm>']} 哈希值为:{hash_.hexdigest()}")

    except ValueError:
        await msg.sendMessage(f"不支持该\"{msg.parsed_msg['<algorithm>']}\"算法")


@hsh.handle('list {受支持的算法列表}')
async def _(msg: Bot.MessageSession):
    await msg.sendMessage('受支持的算法有:\n'+',\n'.join(hashlib.algorithms_available))
