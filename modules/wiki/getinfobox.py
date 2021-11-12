import os
import re
import traceback
import uuid
from typing import Union
from urllib.parse import urljoin

import aiohttp
import ujson as json
from bs4 import BeautifulSoup

from config import Config
from core.logger import Logger

web_render = Config('web_render')


async def get_infobox_pic(link, page_link, headers) -> Union[str, bool]:
    if not web_render or page_link == 'https://wdf.ink/6OUp':
        return False
    try:
        Logger.info('Starting find infobox..')
        wlink = re.sub(r'api.php', '', link)
        link = re.sub(r'(?:w/|)api.php', '', link)
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(page_link, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    html = await req.read()
        except:
            traceback.print_exc()
            return False
        soup = BeautifulSoup(html, 'html.parser')
        pagename = uuid.uuid4()
        url = os.path.abspath(f'./cache/{pagename}.html')
        if os.path.exists(url):
            os.remove(url)
        Logger.info('Downloaded raw.')
        open_file = open(url, 'a', encoding='utf-8')
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
            find_infobox = soup.find(class_='arcaeabox')  # 找 (arcw)
        if find_infobox is None:  # 找
            return False  # 找你妈，不找了<-咱还是回家吧
        Logger.info('Find infobox, start modding...')

        for x in soup.find_all(rel='stylesheet'):
            if x.has_attr('href'):
                x.attrs['href'] = re.sub(';', '&', urljoin(wlink, x.get('href')))
            open_file.write(str(x))

        for x in soup.find_all():
            if x.has_attr('href'):
                x.attrs['href'] = re.sub(';', '&', urljoin(wlink, x.get('href')))
        for x in soup.find_all('style'):
            open_file.write(str(x))

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

        for x in find_infobox.find_all(class_='lazyload'):
            if x.has_attr('class') and x.has_attr('data-src'):
                x.attrs['class'] = 'image'
                x.attrs['src'] = x.attrs['data-src']

        for x in find_infobox.find_all(class_='lazyload'):
            if x.has_attr('class') and x.has_attr('data-src'):
                x.attrs['class'] = 'image'
                x.attrs['src'] = x.attrs['data-src']

        html_lang = soup.find('html').attrs.get('lang')

        open_file.write(f'<body class="mw-parser-output" lang="{html_lang}">')
        open_file.write(str(find_infobox))
        open_file.write('</body>')
        if find_infobox.parent.has_attr('style'):
            open_file.write(join_url(link, find_infobox.parent.get('style')))
        open_file.write('<style>span.heimu a.external,\
span.heimu a.external:visited,\
span.heimu a.extiw,\
span.heimu a.extiw:visited {\
    color: #252525;\
}\
.heimu,\
.heimu a,\
a .heimu,\
.heimu a.new {\
    background-color: #cccccc;\
    text-shadow: none;\
}</style>')
        open_file.close()
        read_file = open(url, 'r', encoding='utf-8')
        html = {'content': read_file.read()}
        Logger.info('Start rendering...')
        picname = os.path.abspath(f'./cache/{pagename}.jpg')
        if os.path.exists(picname):
            os.remove(picname)
        async with aiohttp.ClientSession() as session:
            async with session.post(web_render, headers={
                'Content-Type': 'application/json',
            }, data=json.dumps(html)) as resp:
                with open(picname, 'wb+') as jpg:
                    jpg.write(await resp.read())
        return picname
    except Exception:
        traceback.print_exc()
        return False
