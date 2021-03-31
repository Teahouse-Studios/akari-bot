import asyncio
import json
import os
import re
import traceback
import uuid
import random
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from config import Config


infobox_render = Config().config('infobox_render')


async def get_infobox_pic(link, pagelink, headers, color=False, noise=False, text=False, hueall=False, noiseall=False):
    if noise or noiseall:
        peaceful = f'<svg width="0" height="0"><filter id="filter1"><feTurbulence type="fractalNoise" baseFrequency="0.1" numOctaves="{random.uniform(1, 5)}" /><feDisplacementMap in="SourceGraphic" scale="{random.uniform(2, 5)}" /></filter></svg>'
        normal = f'<svg width="0" height="0"><filter id="filter2"><feTurbulence type="fractalNoise" baseFrequency="{random.uniform(0.1, 0.3)}" numOctaves="{random.uniform(10, 20)}" /><feDisplacementMap in="SourceGraphic" scale="{random.uniform(10, 25)}" /></filter></svg>'
        hard = f'<svg width="0" height="0"><filter id="filter3"><feTurbulence type="fractalNoise" baseFrequency="{random.uniform(0.1, 0.5)}" numOctaves="{random.uniform(20, 40)}" /><feDisplacementMap in="SourceGraphic" scale="{random.uniform(20, 35)}" /></filter></svg>'
        extra = f'<svg width="0" height="0"><filter id="filter4"><feTurbulence type="fractalNoise" baseFrequency="{random.uniform(0.2, 0.9)}" numOctaves="{random.uniform(40, 80)}" /><feDisplacementMap in="SourceGraphic" scale="{random.uniform(40, 55)}" /></filter></svg>'
    if color or hueall:
        color_hue = f'<svg width="0" height="0"><filter id="color1"><feColorMatrix in="SourceGraphic" type="hueRotate" values="180" /></filter></svg>'
        color_alpha = f'<svg width="0" height="0"><filter id="color2"><feColorMatrix in="SourceGraphic" type="luminanceToAlpha" /></filter></svg>'
        color_green = f'<svg width="0" height="0"><filter id="color3"><feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0 1 1 1 1 0 0 0 0 0 0 0 0 0 1 0" /></filter></svg>'
    try:
        print('hello')
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
        print(222)
        find_infobox = soup.find(class_=re.compile('notaninfobox'))  # 我
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_=re.compile('portable-infobox'))  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_=re.compile('infobox'))  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_=re.compile('tpl-infobox'))  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_=re.compile('infoboxtable'))  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_=re.compile('infotemplatebox'))  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_=re.compile('skin-infobox'))  # 找
        if find_infobox is None:  # 找
            find_infobox = soup.find(class_=re.compile('wikitable songtable'))  # 找 (arcw)
        if find_infobox is None:  # 找
            return False  # 找你妈，不找了<-咱还是回家吧
        print('Find infobox..')

        if noiseall:
            r = str(random.randint(0, 4))
            if find_infobox.has_attr('style'):
                try:
                    find_infobox.attrs['style'] = find_infobox.attrs['style'] + (';' if find_infobox.attrs['style'][-1] != ';' else '') + f'filter:url(#filter{r});'
                except:
                    find_infobox.attrs['style'] = find_infobox.attrs['style'] + f'filter:url(#filter{r});'
            else:
                find_infobox.attrs['style'] = f'filter:url(#filter{r});'
        if hueall:
            if find_infobox.has_attr('style'):
                try:
                    find_infobox.attrs['style'] = find_infobox.attrs['style'] + (';' if find_infobox.attrs['style'][-1] != ';' else '') + f'filter:url(#color1);'
                except:
                    find_infobox.attrs['style'] = find_infobox.attrs['style'] + f'filter:url(#color1);'
            else:
                find_infobox.attrs['style'] = f'filter:url(#color1);'

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
            r = str(random.randint(0, 4))
            cr = str(random.randint(0, 3))
            if x.has_attr('href'):
                x.attrs['href'] = join_url(link, x.get('href'))
                if x.has_attr('style'):
                    if r != '0' and noise:
                        if x.attrs['style'].find('filter:url(#filter') == -1:
                            try:
                                x.attrs['style'] = x.attrs['style'] + (
                                    ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#filter{r});'
                            except:
                                x.attrs['style'] = x.attrs['style'] + f'filter:url(#filter{r});'
                    if cr != '0' and color:
                        if x.attrs['style'].find('filter:url(#color') == -1:
                            try:
                                x.attrs['style'] = x.attrs['style'] + (
                                    ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#color{r});'
                            except:
                                x.attrs['style'] = x.attrs['style'] + f'filter:url(#color{r});'
                else:
                    cont = False
                    if r != '0' and noise:
                        x.attrs['style'] = f'filter:url(#filter{r});'
                        cont = True
                    if cr != '0' and cont and color:
                        try:
                            x.attrs['style'] = x.attrs['style'] + (
                                ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#color{r});'
                        except:
                            x.attrs['style'] + f'filter:url(#color{r});'
                    if cr != '0' and color:
                        x.attrs['style'] = f'filter:url(#color{r});'
            elif x.has_attr('src'):
                x.attrs['src'] = join_url(link, x.get('src'))
                if x.has_attr('style'):
                    if r != '0' and noise:
                        if x.attrs['style'].find('filter:url(#filter') == -1:
                            try:
                                x.attrs['style'] = x.attrs['style'] + (
                                    ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#filter{r});'
                            except:
                                x.attrs['style'] = x.attrs['style'] + f'filter:url(#filter{r});'
                    if cr != '0' and color:
                        if x.attrs['style'].find('filter:url(#color') == -1:
                            try:
                                x.attrs['style'] = x.attrs['style'] + (
                                    ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#color{r});'
                            except:
                                x.attrs['style'] = x.attrs['style'] + f'filter:url(#color{r});'
                else:
                    cont = False
                    if r != '0' and noise:
                        x.attrs['style'] = f'filter:url(#filter{r});'
                        cont = True
                    if cr != '0' and cont and color:
                        try:
                            x.attrs['style'] = x.attrs['style'] + (
                                ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#color{r});'
                        except:
                            x.attrs['style'] + f'filter:url(#color{r});'
                    if cr != '0' and color:
                        x.attrs['style'] = f'filter:url(#color{r});'
            elif x.has_attr('srcset'):
                x.attrs['srcset'] = join_url(link, x.get('srcset'))
                if x.has_attr('style'):
                    if r != '0' and noise:
                        if x.attrs['style'].find('filter:url(#filter') == -1:
                            try:
                                x.attrs['style'] = x.attrs['style'] + (
                                    ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#filter{r});'
                            except:
                                x.attrs['style'] = x.attrs['style'] + f'filter:url(#filter{r});'
                    if cr != '0' and color:
                        if x.attrs['style'].find('filter:url(#color') == -1:
                            try:
                                x.attrs['style'] = x.attrs['style'] + (
                                    ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#color{r});'
                            except:
                                x.attrs['style'] = x.attrs['style'] + f'filter:url(#color{r});'
                else:
                    cont = False
                    if r != '0' and noise:
                        x.attrs['style'] = f'filter:url(#filter{r});'
                        cont = True
                    if cr != '0' and cont and color:
                        try:
                            x.attrs['style'] = x.attrs['style'] + (
                                ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#color{r});'
                        except:
                            x.attrs['style'] + f'filter:url(#color{r});'
                    if cr != '0' and color:
                        x.attrs['style'] = f'filter:url(#color{r});'
            elif x.has_attr('style'):
                x.attrs['style'] = re.sub(r'url\(/(.*)\)', 'url(' + link + '\\1)', x.get('style'))
                if x.has_attr('style'):
                    if r != '0' and noise:
                        if x.attrs['style'].find('filter:url(#filter') == -1:
                            try:
                                x.attrs['style'] = x.attrs['style'] + (
                                    ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#filter{r});'
                            except:
                                x.attrs['style'] = x.attrs['style'] + f'filter:url(#filter{r});'
                    if cr != '0' and color:
                        if x.attrs['style'].find('filter:url(#color') == -1:
                            try:
                                x.attrs['style'] = x.attrs['style'] + (
                                    ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#color{r});'
                            except:
                                x.attrs['style'] = x.attrs['style'] + f'filter:url(#color{r});'
                else:
                    cont = False
                    if r != '0' and noise:
                        x.attrs['style'] = f'filter:url(#filter{r});'
                        cont = True
                    if cr != '0' and cont and color:
                        try:
                            x.attrs['style'] = x.attrs['style'] + (
                                ';' if x.attrs['style'][-1] != ';' else '') + f'filter:url(#color{r});'
                        except:
                            x.attrs['style'] + f'filter:url(#color{r});'
                    if cr != '0' and color:
                        x.attrs['style'] = f'filter:url(#color{r});'

        for x in find_infobox.find_all(text=re.compile(r'.*')):
            r = str(random.randint(0, 4))
            cr = str(random.randint(0, 3))
            tr = str(random.randint(0, 2))

            if x not in ['', '\n', None]:
                if x.parent.has_attr('style') and x.parent.has_attr('style') not in ['', '\n', 'None']:
                    if r != '0' and noise:
                        if x.parent.attrs['style'].find('filter:url(#filter') == -1:
                            try:
                                x.parent.attrs['style'] = x.parent.attrs['style'] + (
                                    ';' if x.parent.attrs['style'][-1] != ';' else '') + f'filter:url(#filter{r});'
                            except:
                                x.parent.attrs['style'] = x.parent.attrs['style'] + f'filter:url(#filter{r});'
                    if cr != '0' and color:
                        if x.parent.attrs['style'].find('filter:url(#color') == -1:
                            try:
                                x.parent.attrs['style'] = x.parent.attrs['style'] + (
                                    ';' if x.parent.attrs['style'][-1] != ';' else '') + f'filter:url(#color{cr});'
                            except:
                                x.parent.attrs['style'] = x.parent.attrs['style'] + f'filter:url(#color{r});'
                    if tr != '0' and text:
                        trr = random.randint(0, 10)
                        if trr == 2:
                            x.replace_with(re.sub(r'.', 'eeeeeee', x))
                        if trr == 1:
                            x.replace_with(re.sub(r'.', '■■□■e■□■¿', x))
                        if trr == 6:
                            x.replace_with(re.sub(r'.', '↓□□↓□□□□¿', x))
                        if trr == 5:
                            x.replace_with(re.sub(r'.', '↓↓↑↓↓↓↑↓↑↓', x))
                        if trr == 8:
                            x.replace_with(re.sub(r'.', '¿¿¿¿¿¿¿¿¿', x))
                        if trr == 7:
                            x.replace_with(re.sub(r'.', '棍斤拷棍斤拷棍斤拷', x))
                        if trr == 10:
                            x.replace_with(re.sub(r'.', '烫烫烫烫烫烫烫烫烫', x))
                else:
                    cont = False
                    if r != '0' and noise:
                        x.parent.attrs['style'] = f'filter:url(#filter{r});'
                        cont = True
                    if cr != '0' and cont and color:
                        try:
                            x.parent.attrs['style'] = x.parent.attrs['style'] + (
                                ';' if x.parent.attrs['style'][-1] != ';' else '') + f'filter:url(#color{cr});'
                        except:
                            x.parent.attrs['style'] = x.parent.attrs['style'] + f'filter:url(#color{r});'
                    if cr != '0' and color:
                        x.parent.attrs['style'] = f'filter:url(#color{r});'
                    if tr != '0' and text:
                        trr = random.randint(0, 10)
                        if trr == 2:
                            x.replace_with(re.sub(r'.', 'eeeeeee', x))
                        if trr == 1:
                            x.replace_with(re.sub(r'.', '■■■■', x))
                        if trr == 3:
                            x.replace_with(re.sub(r'.', '爬', x))
                        if trr == 4:
                            x.replace_with(re.sub(r'.', '□¿¿¿¿¿¿□¿¿¿', x))
                        if trr == 6:
                            x.replace_with(re.sub(r'.', '□□□□□□□□□', x))
                        if trr == 7:
                            x.replace_with(re.sub(r'.', '□■棍斤拷棍斤拷棍斤拷', x))
                        if trr == 10:
                            x.replace_with(re.sub(r'.', '■烫烫烫烫烫烫烫烫烫', x))

        replace_link = find_infobox

        if infobox_render is None:
            open_file.write(str(replace_link))
            open_file.close()
        else:
            html_list.append(str(replace_link))
            if noise or noiseall:
                html_list.append(peaceful)
                html_list.append(normal)
                html_list.append(hard)
                html_list.append(extra)
            if color or hueall:
                html_list.append(color_hue)
                html_list.append(color_alpha)
                html_list.append(color_green)
            html = '\n'.join(html_list)
            html = {'content': html}
        print(html)
        print('getting rendered page..')

        path2 = os.path.abspath('./assets/chromedriver.exe')
        picname = os.path.abspath(f'./cache/{pagename}.jpg')
        if os.path.exists(picname):
            os.remove(picname)
        if infobox_render is not None:
            async with aiohttp.ClientSession() as session:
                async with session.post(infobox_render, headers={
                    'Content-Type': 'application/json',
                }, data=json.dumps(html)) as resp:
                    with open(picname, 'wb+') as jpg:
                        jpg.write(await resp.read())
            return picname
        desired_capabilities = DesiredCapabilities.CHROME
        desired_capabilities["pageLoadStrategy"] = "none"
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        driver = webdriver.Chrome(path2, options=options)
        driver.set_window_size(500, 400)
        js_height = "return document.body.clientHeight"

        link = url
        print(link)
        driver.get(link)
        await asyncio.sleep(1)
        k = 1
        height = driver.execute_script(js_height)
        while True:
            if k * 500 < height:
                js_move = "window.scrollTo(0,{})".format(k * 500)
                print(js_move)
                driver.execute_script(js_move)
                await asyncio.sleep(1)
                height = driver.execute_script(js_height)
                k += 1
            else:
                break
        scroll_width = driver.execute_script('return document.body.parentNode.scrollWidth')
        scroll_height = driver.execute_script('return document.body.parentNode.scrollHeight')
        driver.set_window_size(scroll_width, scroll_height)
        driver.get_screenshot_as_file(picname)
        driver.close()
        return picname
    except Exception:
        traceback.print_exc()
        return False
