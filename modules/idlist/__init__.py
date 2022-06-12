import re
import urllib.parse

from core.component import on_command
from core.elements import MessageSession
from core.utils import get_url

enums = ['block', 'item', 'entity', 'effect', 'enchant', 'fog', 'location', 'entityevent', 'entityfamily', 'animation',
         'animationcontroller', 'particleemitter', 'sound', 'gamerule', 'entityslot', 'loottable', 'music',
         'summonableentity', 'loottool']
enumNames = ['方块', '物品', '实体', '状态效果', '附魔类型', '迷雾', '结构', '实体事件', '实体族', '动画', '动画控制器', '粒子发射器',
             '声音', '游戏规则', '槽位类型', '战利品表', '音乐', '可再生的实体', '战利品使用工具']
enum_map = dict(zip(enumNames, enums))
branches = ['vanilla', 'education', 'experiment', 'translator']
api = 'https://ca.projectxero.top/idlist/search'

i = on_command('idlist')


@i.handle('<query> [<filter>...] {查询MCBEID表。}')
async def _(msg: MessageSession):
    query = msg.parsed_msg['<query>']
    filter = msg.parsed_msg['<filter>']
    enum = []
    version = []
    branch = []
    for x in filter:
        if x.lower() in enums:
            enum.append(x)
        elif re.match(r'[0-9].*\.[0-9].*\.[0-9].*\.[0-9]', x):
            version.append(x)
        elif x.lower() in branches:
            branch.append(x)
        elif x in enum_map:
            enum.append(enum_map[x])
        else:
            if not enum and not version and not branch:
                query += " " + x
    if len(enum) > 1:
        return await msg.sendMessage('你一次只能指定一个枚举类型。')
    if len(version) > 1:
        return await msg.sendMessage('你一次只能指定一个版本。')
    if len(branch) > 1:
        return await msg.sendMessage('你一次只能指定一个分支。')
    query_options = {'q': query, 'limit': '6'}
    if enum:
        query_options['enum'] = enum[0]
    if version:
        query_options['version'] = version[0]
    if branch:
        query_options['branch'] = branch[0]
    query_url = api + '?' + urllib.parse.urlencode(query_options)
    resp = await get_url(query_url, fmt='json')
    print(resp)
    result = resp['data']['result']
    plain_texts = []
    if result:
        for x in result[0:5]:
            plain_texts.append(f'{x["enumName"]}：{x["key"]} -> {x["value"]}')
        if resp['data']['count'] > 5:
            plain_texts.append('...仅显示前5条结果。')
        await msg.finish('\n'.join(plain_texts))
    else:
        await msg.finish('没有找到结果。')



