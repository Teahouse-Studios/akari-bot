import itertools
import re
from ast import literal_eval

from core.builtins import Bot, BotDBUtil
from core.component import module
from .server import server

inf = module('info', alias={'s': 'info url', 'server': 'info url'}, developers='haoye_qwq',
                 desc='Minecraft服务器信息模块')


# def write(id_group: str, data: dict):
#     json_data = json.dumps(data)
#     db.set(f"{id_group}_info", json_data)
#
#
# def read(id_group: str):
#     data = db.get(f"{id_group}_info")
#     return json.loads(data)
#
#
# def exist(id_group: str):
#     return db.exists(f"{id_group}_info")
#
#
# def reset(id_group: str):
#     if exist(id_group):
#         db.delete(f"{id_group}_info")
#
#
# def delete(id_group: str, name: str):
#     dicts = read(id_group)
#     if name in dicts:
#         del dicts[name]
#         write(id_group, dicts)
#         return True
#     else:
#         return False


# def is_json(json_):
#     try:
#         json.loads(json_)
#     except ValueError:
#         return False
#     return True

info_ = BotDBUtil.InfoServers


@inf.handle('bind <name> <ServerUrl> {绑定服务器}', required_admin=True)
async def _(msg: Bot.MessageSession):
    group_id = msg.target.target_id
    name = msg.parsed_msg['<name>']
    serip = msg.parsed_msg['<ServerUrl>']
    if not info_.exist(id_group=group_id):
        info_.write(id_group=group_id, data={name: serip})
    else:
        dicts = info_.read(id_group=group_id)
        dicts[name] = serip
        info_.write(id_group=group_id, data=dicts)
    await msg.sendMessage('添加成功')


@inf.handle('reset {重置已绑定服务器列表}', required_admin=True)
async def _____(msg: Bot.MessageSession):
    group_id = msg.target.target_id
    confirm = await msg.waitConfirm('你确定要删除它们吗?很久才能找回来!(真的很久!)')
    if confirm:
        info_.reset(id_group=group_id)
        await msg.sendMessage('已重置')
    else:
        await msg.sendMessage('已取消')


@inf.handle('list {查看已绑定服务器列表}')
async def __(msg: Bot.MessageSession):
    group_id = msg.target.target_id
    if info_.exist(id_group=group_id):
        list_ = re.sub(r'[{}]', '', str(info_.read(id_group=group_id))).replace('\'', '').replace(', ', ',\n').replace(': ', ' —> ')
        await msg.sendMessage('服务器列表:\n' + list_)
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
    group_id = msg.target.target_id
    if info_.exist(id_group=group_id) and name in info_.read(id_group=group_id):
        info = await server(info_.read(id_group=group_id)[name])
        send = await msg.sendMessage(info + '\n[90秒后撤回]')
        await msg.sleep(90)
        await send.delete()
    else:
        send = await msg.sendMessage('服务器不存在，请检查输入\n[90秒后撤回]')
        await msg.sleep(90)
        await send.delete()


@inf.handle('unbind <name> {取消绑定服务器}', required_admin=True)
async def ______(msg: Bot.MessageSession):
    name = msg.parsed_msg['<name>']
    group_id = msg.target.target_id
    unbind = info_.delete(id_group=group_id, name=name)
    if unbind:
        await msg.sendMessage('已删除')
    else:
        await msg.sendMessage('服务器不存在，请检查输入')


@inf.handle('multi_bind <dict> {绑定多个服务器}', required_superuser=True)
async def _______(msg: Bot.MessageSession):
    group_id = msg.target.target_id
    fetched = literal_eval(str(msg.parsed_msg['<dict>']).replace('\n', ''))
    if info_.exist(id_group=group_id):
        info_.write(id_group=group_id, data=dict(itertools.chain(
            info_.read(group_id).items(), fetched.items()
        )))
        await msg.sendMessage(f"已成功添加:\n{str(fetched.keys())}")
    elif not info_.exist(id_group=group_id):
        info_.write(id_group=group_id, data=fetched)
        await msg.sendMessage(f"已成功添加:\n{str(fetched.keys())}")
