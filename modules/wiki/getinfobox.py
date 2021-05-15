import json
import os
import re
import traceback
import uuid
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from config import Config
from core.template import logger_info

infobox_render = Config('infobox_render')


async def get_infobox_pic(link, pagelink, headers):
    try:
        logger_info('Starting find infobox..')
        wlink = re.sub(r'api.php', '', link)
        link = re.sub(r'(?:w/|)api.php', '', link)
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(pagelink, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    html = await req.read()
        except:
            traceback.print_exc()
            return False
        soup = BeautifulSoup(html, 'html.parser')
        pagename = uuid.uuid4()
        url = os.path.abspath(f'./cache/{pagename}.html')
        if os.path.exists(url):
            os.remove(url)
        logger_info('Downloaded raw.')
        find_infobox = soup.find(class_='notaninfobox')  # 我
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_='portable-infobox')  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_='infobox')  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_='tpl-infobox')  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_='infoboxtable')  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_='infotemplatebox')  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_='skin-infobox')  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(id_='songbox')  # 找 (arcw)
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_='songtable')  # 找 (arcw)
        if find_infobox is None:  # 找
            return False  # 找你妈，不找了<-咱还是回家吧
        logger_info('Find infobox, start modding...')

        if infobox_render is None:
            open_file = open(url, 'a', encoding='utf-8')
        else:
            html_list = []

        for x in soup.find_all(rel='stylesheet'):
            y = str(x.get('href'))
            z = urljoin(wlink, y)
            z = re.sub(';', '&', z)
            if infobox_render is None:
                open_file.write(f'<link href="{z}" rel="stylesheet"/>\n')
            else:
                html_list.append(f'<link href="{z}" rel="stylesheet"/>\n')

        def join_url(base, target):
            target = target.split(' ')
            targetlist = []
            for x in target:
                if x.find('/') != -1:
                    x = urljoin(base, x)
                    targetlist.append(x)
                else:
                    targetlist.append(x)
            target = ' '.join(targetlist)
            return target

        for x in find_infobox.find_all(['a', 'img', 'span']):
            if x.has_attr('href'):
                x.attrs['href'] = join_url(link, x.get('href'))
            if x.has_attr('src'):
                x.attrs['src'] = join_url(link, x.get('src'))
            if x.has_attr('srcset'):
                x.attrs['srcset'] = join_url(link, x.get('srcset'))
            if x.has_attr('style'):
                x.attrs['style'] = re.sub(r'url\(/(.*)\)', 'url(' + link + '\\1)', x.get('style'))
        replace_link = find_infobox

        if infobox_render is None:
            open_file.write(str(replace_link))
            open_file.close()
        else:
            html_list.append(str(replace_link))
            html = '\n'.join(html_list)
            html = {'content': html}
        logger_info('Start rendering...')
        picname = os.path.abspath(f'./cache/{pagename}.jpg')
        if os.path.exists(picname):
            os.remove(picname)
        async with aiohttp.ClientSession() as session:
            async with session.post(infobox_render, headers={
                'Content-Type': 'application/json',
            }, data=json.dumps(html)) as resp:
                with open(picname, 'wb+') as jpg:
                    jpg.write(await resp.read())
        return picname
    except Exception:
        traceback.print_exc()
        return False
