from core.builtins import Bot
from core.component import on_command
from config import Config
from .server import server
import redis
import ujson as json

inf = on_command('info', alias={'s': 'info url', 'server': 'info url'}, developers='haoye_qwq',
                 desc='Minecraft服务器信息模块')
redis_ = Config('redis').split(':')
db = redis.StrictRedis(host=redis_[0], port=int(redis_[1]), db=0, decode_responses=True)


def write(id_group: str, data: dict):
    json_data = json.dumps(data)
    db.set(f"{id_group}_info", json_data)


def read(id_group: str):
    data = db.get(f"{id_group}_info")
    return json.loads(data)


def exist(id_group: str):
    return db.exists(f"{id_group}_info")


@inf.handle('set <name> <ServerUrl> {添加服务器}', required_admin=True)
async def _(msg: Bot.MessageSession):
    group_id = msg.target.targetId
    name = msg.parsed_msg['<name>']
    serip = msg.parsed_msg['<ServerUrl>']
    if not exist(group_id):
        write(group_id, {name: serip, 'list': [name]})
    else:
        dicts = read(group_id)
        dicts[name] = serip
        dicts['list'] = list(set(dicts['list'].append(name)))
    await msg.sendMessage('添加成功')


@inf.handle('reset {重置服务器列表}')
async def _____(msg: Bot.MessageSession):
    group_id = msg.target.targetId
    db.delete(f"{group_id}_list")


@inf.handle('list {查看服务器列表}')
async def __(msg: Bot.MessageSession):
    group_id = msg.target.targetId
    if exist(group_id):
        list_ = read(group_id)['list']
        await msg.sendMessage('服务器列表:\n' + ',\n'.join(list_))
    else:
        await msg.sendMessage('列表中暂无服务器，请先绑定')


@inf.handle('url <ServerUrl> {查询任意服务器信息}')
async def ___(msg: Bot.MessageSession):
    info = await server(msg.parsed_msg['<ServerUrl>'])
    send = await msg.sendMessage(info + '\n[90秒后撤回]')
    await msg.sleep(90)
    await send.delete()


@inf.handle('<name> {查询已绑定的服务器信息}')
async def ____(msg: Bot.MessageSession):
    name = msg.parsed_msg['<name>']
    group_id = msg.target.targetId
    if exist(group_id) and name in read(group_id):
        info = await server(read(group_id)[name])
        send = await msg.sendMessage(info + '\n[90秒后撤回]')
        await msg.sleep(90)
        await send.delete()
    else:
        send = await msg.sendMessage('服务器不存在，请检查输入\n[90秒后撤回]')
        await msg.sleep(90)
        await send.delete()
