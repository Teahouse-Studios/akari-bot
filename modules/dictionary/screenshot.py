import os
import re
import traceback
import uuid
from typing import Union
from urllib.parse import urljoin

import aiohttp
import ujson as json
from bs4 import BeautifulSoup

from config import CFG
from core.logger import Logger

web_render = CFG.get_url('web_render')
web_render_local = CFG.get_url('web_render_local')


async def get_pic(link, source, use_local=True) -> Union[str, bool]:
    if not web_render_local:
        if not web_render:
            Logger.warn('[Webrender] Webrender is not configured.')
            return False
        use_local = False
    try:
        Logger.info('Starting find section...')
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get((web_render_local if use_local else web_render) + 'source?url=' + link,
                                       timeout=aiohttp.ClientTimeout(total=20)) as req:
                    html = await req.read()
        except BaseException:
            traceback.print_exc()
            return False
        soup = BeautifulSoup(html, 'html.parser')
        pagename = uuid.uuid4()
        url = os.path.abspath(f'./cache/{pagename}.html')
        if os.path.exists(url):
            os.remove(url)
        Logger.info('Downloaded raw.')
        open_file = open(url, 'a', encoding='utf-8')

        def join_url(base, target):
            target = target.split(' ')
            targetlist = []
            for x in target:
                if x.find('/') != -1:
                    x = urljoin(base, x)
                targetlist.append(x)
            target = ' '.join(targetlist)
            return target

        open_file.write('<!DOCTYPE html>\n')
        for x in soup.find_all('html'):
            fl = []
            for f in x.attrs:
                if isinstance(x.attrs[f], str):
                    fl.append(f'{f}="{x.attrs[f]}"')
                elif isinstance(x.attrs[f], list):
                    fl.append(f'{f}="{" ".join(x.attrs[f])}"')
            open_file.write(f'<html {" ".join(fl)}>')

        open_file.write('<head>\n')
        for x in soup.find_all(rel='stylesheet'):
            if x.has_attr('href'):
                x.attrs['href'] = re.sub(
                    ';', '&', urljoin(link, x.get('href')))
            open_file.write(str(x))

        for x in soup.find_all():
            if x.has_attr('href'):
                x.attrs['href'] = re.sub(
                    ';', '&', urljoin(link, x.get('href')))
        open_file.write('</head>')

        for x in soup.find_all('style'):
            open_file.write(str(x))

        for x in soup.find_all('body'):
            if x.has_attr('class'):
                open_file.write(
                    f'<body class="{" ".join(x.get("class"))}">')

        for x in soup.find_all(['a', 'img', 'span']):
            if x.has_attr('href'):
                x.attrs['href'] = join_url(link, x.get('href'))
            if x.has_attr('src'):
                x.attrs['src'] = join_url(link, x.get('src'))
            if x.has_attr('srcset'):
                x.attrs['srcset'] = join_url(link, x.get('srcset'))
            if x.has_attr('style'):
                x.attrs['style'] = re.sub(
                    r'url\(/(.*)\)', 'url(' + link + '\\1)', x.get('style'))
        if source == 'collins':
            open_file.write('<div id="main_content" class="he dc page">')
            content = soup.select_one(
                '.dictionaries > .dictionary, .dictionaries.dictionary')
            trash = content.select(
                '.hwd_sound, .cobuild-logo, .pronIPASymbol, .title_frequency_container')
            if trash:
                for x in trash:
                    x.decompose()
        elif source == 'yd':
            open_file.write('<div class="simple basic">')
            content = soup.select_one('.basic')
        else:
            return False
        open_file.write(str(content))
        w = 1000
        open_file.write('</div></body>')
        open_file.write('</html>')
        open_file.close()
        read_file = open(url, 'r', encoding='utf-8')
        html = {'content': read_file.read(), 'width': w}
        Logger.info('Start rendering...')
        picname = os.path.abspath(f'./cache/{pagename}.jpg')
        if os.path.exists(picname):
            os.remove(picname)
        async with aiohttp.ClientSession() as session:
            async with session.post((web_render_local if use_local else web_render), headers={
                'Content-Type': 'application/json',
            }, data=json.dumps(html)) as resp:
                with open(picname, 'wb+') as jpg:
                    jpg.write(await resp.read())
        return picname
    except Exception:
        traceback.print_exc()
        return False
