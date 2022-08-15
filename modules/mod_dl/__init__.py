import re
import urllib.parse

from bs4 import BeautifulSoup

from core.builtins.message import MessageSession
from core.component import on_command
from core.utils import get_url

mod_dl = on_command(
    bind_prefix='mod_dl',
    desc='下载CurseForge上的Mod。',
    developers=['HornCopper', 'OasisAkari'],
    recommend_modules=['mcmod'],
    alias='moddl')


def cn_chk(string: str):
    for word in string:
        if u'\u4e00' <= word <= u'\u9fff':
            return True
    return False


source_url = 'https://files.xmdhs.com/curseforge/'


@mod_dl.handle('<mod_name> [<version>] {通过模组名获取模组下载链接，CloudFlare CDN支持。}')
async def main(msg: MessageSession):
    mod_name = msg.parsed_msg['<mod_name>']
    ver = msg.parsed_msg.get('<version>', False)
    if ver:
        match_ver = re.match(r'^\d+\.\d+\.\d+$|^\d+\.\d+$|\d+w\d+[abcd]', ver)
        if match_ver is None:
            mod_name += ' ' + ver
            ver = False
    if cn_chk(mod_name):
        return {'msg': 'CurseForge暂不支持中文搜索。', 'success': False}
    full_url = f'{source_url}s?q={urllib.parse.quote(mod_name)}&type=1'
    try:
        html = await get_url(full_url, status_code=200)
        bs = BeautifulSoup(html, 'html.parser')
        information = bs.body.div.div
        infos = {}
        for x in information.find_all('a'):
            infos[x.find('h3').text] = x.get('href')
        if len(infos) > 1:
            reply_text = []
            i = 0
            for info in infos:
                i += 1
                reply_text.append(f'{i}. {info}')
            reply = await msg.waitReply('搜索结果如下：\n' + '\n'.join(reply_text) + '\n请回复编号来选择mod。')
            replied = reply.asDisplay()
            if replied.isdigit():
                replied = int(replied)
                if replied > len(infos):
                    return await msg.finish('编号超出范围。')
                else:
                    mod_url = infos[list(infos.keys())[replied - 1]]
            else:
                return await msg.finish('无效的编号，必须为纯数字。')
        else:
            mod_url = infos[list(infos.keys())[0]]
        html_2 = await get_url(f'{source_url}{mod_url[1:]}', status_code=200)
        bs_2 = BeautifulSoup(html_2, 'html.parser')
        information_2 = bs_2.body.div.div
        infos_2 = {}
        for x in information_2.find_all('a'):
            infos_2[x.find('h3').text] = x.get('href')
        if ver:
            if ver in infos_2:
                mod_url_2 = infos_2[ver]
            else:
                return await msg.finish('没有找到指定版本的模组。')
        else:
            reply_text = []
            for info2 in infos_2:
                reply_text.append(f'{info2}')
            reply2 = await msg.waitReply('此mod拥有如下版本：\n' + '\n'.join(reply_text) + '\n请回复版本号来选择版本。')
            replied2 = reply2.asDisplay()
            if replied2 in infos_2:
                mod_url_2 = infos_2[replied2]
                ver = replied2
            else:
                return await msg.finish('无效的版本号。')
        url_3 = source_url + mod_url_2[1:]
        html_3 = await get_url(url_3, status_code=200)
        bs_3 = BeautifulSoup(html_3, 'html.parser')
        infos = {'normal': {}, 'fabric': {}, 'forge': {}}
        information_3 = bs_3.find_all('tr')
        for x in information_3[1:]:
            tbs = x.find_all('td')
            mod = tbs[0].find('a')
            status = tbs[1].text
            name = mod.text
            depends = tbs[3].find_all('a')
            mod_type = 'normal'
            if name.lower().find('fabric') != -1:
                mod_type = 'fabric'
            elif name.lower().find('forge') != -1:
                mod_type = 'forge'
            if status not in infos[mod_type]:
                infos[mod_type][status] = {'url': mod.get('href'), 'depends': len(depends), 'name': name}
        send_ = []
        for x in infos:
            for y in infos[x]:
                send_.append((f'{x.title()} ({y})：\n' if x != 'normal' else f'{y}：\n') +
                             f'下载链接：{infos[x][y]["url"]}\n'
                             f'文件名：{infos[x][y]["name"]}\n' +
                             (f'此mod共有{str(infos[x][y]["depends"])}个依赖，请确认是否已经下载：\n{url_3}' if infos[x][y][
                                                                                                   "depends"] > 0 else ''))
        await msg.finish('\n'.join(send_))

    except ValueError:  # 404 ...
        await msg.finish('未找到该Mod。')
