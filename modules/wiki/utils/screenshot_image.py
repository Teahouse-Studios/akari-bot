import os
import re
import traceback
import uuid
from typing import Union, List
from urllib.parse import urljoin

import aiohttp
import ujson as json
from bs4 import BeautifulSoup, Comment

from core.logger import Logger
from core.utils.http import download_to_cache
from core.utils.web_render import WebRender, webrender

elements = ['.notaninfobox', '.portable-infobox', '.infobox', '.tpl-infobox', '.infoboxtable', '.infotemplatebox',
            '.skin-infobox', '.arcaeabox', '.moe-infobox', '.rotable']
assets_path = os.path.abspath('./assets/')


async def generate_screenshot_v2(page_link, section=None, allow_special_page=False, content_mode=False, use_local=True,
                                 element=None):
    elements_ = elements.copy()
    if element and isinstance(element, List):
        elements_ += element
    if not WebRender.status:
        return False
    elif not WebRender.local:
        use_local = False
    if not section:
        if allow_special_page and content_mode:
            elements_.insert(0, '.mw-body-content')
        if allow_special_page and not content_mode:
            elements_.insert(0, '.diff')
        Logger.info('[Webrender] Generating element screenshot...')
        try:
            img = await download_to_cache(webrender('element_screenshot', use_local=use_local),
                                          status_code=200,
                                          headers={'Content-Type': 'application/json'},
                                          method="POST",
                                          post_data=json.dumps({
                                              'url': page_link,
                                              'element': elements_}),
                                          attempt=1,
                                          timeout=30,
                                          request_private_ip=True
                                          )
        except aiohttp.ClientConnectorError:
            if use_local:
                return await generate_screenshot_v2(page_link, section, allow_special_page, content_mode,
                                                    use_local=False)
            else:
                return False
        except ValueError:
            Logger.info('[Webrender] Generation Failed.')
            return False
    else:
        Logger.info('[Webrender] Generating section screenshot...')
        try:
            img = await download_to_cache(webrender('section_screenshot', use_local=use_local),
                                          status_code=200,
                                          headers={'Content-Type': 'application/json'},
                                          method="POST",
                                          post_data=json.dumps({
                                              'url': page_link,
                                              'section': section}),
                                          attempt=1,
                                          timeout=30,
                                          request_private_ip=True
                                          )
        except aiohttp.ClientConnectorError:
            if use_local:
                return await generate_screenshot_v2(page_link, section, allow_special_page, content_mode,
                                                    use_local=False)
            else:
                return False
        except ValueError:
            Logger.info('[Webrender] Generation Failed.')
            return False

    return img


async def generate_screenshot_v1(link, page_link, headers, use_local=True, section=None, allow_special_page=False) -> Union[str, bool]:
    if not WebRender.status:
        return False
    elif not WebRender.local:
        use_local = False
    try:
        Logger.info('Starting find infobox/section..')
        if link[-1] != '/':
            link += '/'
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(page_link, timeout=aiohttp.ClientTimeout(total=20)) as req:
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
        timeless_fix = False

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
                get_herf = x.get('href')
                if get_herf.find('timeless') != -1:
                    timeless_fix = True
                x.attrs['href'] = re.sub(';', '&', urljoin(link, get_herf))
            open_file.write(str(x))

        for x in soup.find_all():
            if x.has_attr('href'):
                x.attrs['href'] = re.sub(';', '&', urljoin(link, x.get('href')))
        open_file.write('</head>')

        for x in soup.find_all('style'):
            open_file.write(str(x))

        if not section:
            find_diff = None
            if allow_special_page:
                find_diff = soup.find('table', class_=re.compile('diff'))
                if find_diff:
                    Logger.info('Found diff...')
                    for x in soup.find_all('body'):
                        if x.has_attr('class'):
                            open_file.write(f'<body class="{" ".join(x.get("class"))}">')

                    for x in soup.find_all('div'):
                        if x.has_attr('id'):
                            if x.get('id') in ['content', 'mw-content-text']:
                                fl = []
                                for f in x.attrs:
                                    if isinstance(x.attrs[f], str):
                                        fl.append(f'{f}="{x.attrs[f]}"')
                                    elif isinstance(x.attrs[f], list):
                                        fl.append(f'{f}="{" ".join(x.attrs[f])}"')
                                open_file.write(f'<div {" ".join(fl)}>')
                    open_file.write('<div class="mw-parser-output">')

                    for x in soup.find_all('main'):
                        fl = []
                        for f in x.attrs:
                            if isinstance(x.attrs[f], str):
                                fl.append(f'{f}="{x.attrs[f]}"')
                            elif isinstance(x.attrs[f], list):
                                fl.append(f'{f}="{" ".join(x.attrs[f])}"')
                        open_file.write(f'<main {" ".join(fl)}>')
                    open_file.write(str(find_diff))
                    w = 2000
            if not find_diff:
                infoboxes = elements.copy()
                find_infobox = None
                for i in infoboxes:
                    find_infobox = soup.find(class_=i[1:])
                    if find_infobox:
                        break
                if not find_infobox:
                    Logger.info('Found nothing...')
                    return False
                else:
                    Logger.info('Found infobox...')

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

                    open_file.write('<div class="mw-parser-output">')

                    open_file.write(str(find_infobox))
                    w = 500
                    open_file.write('</div>')
        else:
            for x in soup.find_all('body'):
                if x.has_attr('class'):
                    open_file.write(f'<body class="{" ".join(x.get("class"))}">')

            for x in soup.find_all('div'):
                if x.has_attr('id'):
                    if x.get('id') in ['content', 'mw-content-text']:
                        fl = []
                        for f in x.attrs:
                            if isinstance(x.attrs[f], str):
                                fl.append(f'{f}="{x.attrs[f]}"')
                            elif isinstance(x.attrs[f], list):
                                fl.append(f'{f}="{" ".join(x.attrs[f])}"')
                        open_file.write(f'<div {" ".join(fl)}>')

            open_file.write('<div class="mw-parser-output">')

            for x in soup.find_all('main'):
                fl = []
                for f in x.attrs:
                    if isinstance(x.attrs[f], str):
                        fl.append(f'{f}="{x.attrs[f]}"')
                    elif isinstance(x.attrs[f], list):
                        fl.append(f'{f}="{" ".join(x.attrs[f])}"')
                open_file.write(f'<main {" ".join(fl)}>')

            def is_comment(e):
                return isinstance(e, Comment)

            to_remove = soup.find_all(text=is_comment)
            for element in to_remove:
                element.extract()
            selected = False
            x = None
            hx = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
            selected_hx = None
            for h in hx:
                if selected:
                    break
                for x in soup.find_all(h):
                    for y in x.find_all('span', id=section):
                        if y != '':
                            selected = True
                            selected_hx = h
                            break
                    if selected:
                        break
            if not selected:
                Logger.info('Found nothing...')
                return False
            Logger.info('Found section...')
            open_file.write(str(x))
            b = x
            bl = []
            while True:
                b = b.next_sibling
                if not b:
                    break

                if b.name == selected_hx:
                    break
                if b.name in hx:
                    if hx.index(selected_hx) >= hx.index(b.name):
                        break
                if b not in bl:
                    bl.append(str(b))
            open_file.write(''.join(bl))
            open_file.close()
            open_file = open(url, 'r', encoding='utf-8')
            soup = BeautifulSoup(open_file.read(), 'html.parser')
            open_file.close()

            for x in soup.find_all(['a', 'img', 'span']):
                if x.has_attr('href'):
                    x.attrs['href'] = join_url(link, x.get('href'))
                if x.has_attr('src'):
                    x.attrs['src'] = join_url(link, x.get('src'))
                if x.has_attr('srcset'):
                    x.attrs['srcset'] = join_url(link, x.get('srcset'))
                if x.has_attr('style'):
                    x.attrs['style'] = re.sub(r'url\(/(.*)\)', 'url(' + link + '\\1)', x.get('style'))

            for x in soup.find_all(class_='lazyload'):
                if x.has_attr('class') and x.has_attr('data-src'):
                    x.attrs['class'] = 'image'
                    x.attrs['src'] = x.attrs['data-src']

            for x in soup.find_all(class_='lazyload'):
                if x.has_attr('class') and x.has_attr('data-src'):
                    x.attrs['class'] = 'image'
                    x.attrs['src'] = x.attrs['data-src']
            open_file = open(url, 'w', encoding='utf-8')
            open_file.write(str(soup))
            w = 1000
            open_file.write('</div></body>')
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
        if timeless_fix:
            open_file.write('<style>body {\
                            background: white!important}</style>')
        open_file.write('</html>')
        open_file.close()
        read_file = open(url, 'r', encoding='utf-8')
        html = {'content': read_file.read(), 'width': w, 'mw': True}
        Logger.info('Start rendering...')
        picname = os.path.abspath(f'./cache/{pagename}.jpg')
        if os.path.exists(picname):
            os.remove(picname)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webrender(), headers={
                    'Content-Type': 'application/json',
                }, data=json.dumps(html)) as resp:
                    if resp.status != 200:
                        Logger.info(f'Failed to render: {await resp.text()}')
                        return False
                    with open(picname, 'wb+') as jpg:
                        jpg.write(await resp.read())
        except aiohttp.ClientConnectorError:
            if use_local:
                async with aiohttp.ClientSession() as session:
                    async with session.post(webrender(use_local=False), headers={
                        'Content-Type': 'application/json',
                    }, data=json.dumps(html)) as resp:
                        if resp.status != 200:
                            Logger.info(f'Failed to render: {await resp.text()}')
                            return False
                        with open(picname, 'wb+') as jpg:
                            jpg.write(await resp.read())
        return picname
    except Exception:
        traceback.print_exc()
        return False
