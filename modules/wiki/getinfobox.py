import asyncio
import json
import os
import re
import traceback
import uuid
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from config import Config

config_path = os.path.abspath('./config/config.cfg')

try:
    if config_path:
        infobox_render = Config().config(config_path, 'infobox_render')
except:
    infobox_render = None


async def get_infobox_pic(link, pagelink, headers):
    try:
        print('hello')
        wlink = re.sub(r'api.php', '', link)
        link = re.sub(r'(?:w/|)api.php', '', link)
        print(link)
        print(pagelink)
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(pagelink, timeout=aiohttp.ClientTimeout(total=20)) as req:
                    html = await req.read()
        except:
            traceback.print_exc()
            return False
        print(111)
        soup = BeautifulSoup(html, 'html.parser')
        pagename = uuid.uuid4()
        url = os.path.abspath(f'./cache/{pagename}.html')
        if os.path.exists(url):
            os.remove(url)
        print(222)
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
            find_infobox = soup.find(class_='wikitable songtable')  # 找 (arcw)
        if find_infobox is None:  # 找
            return False  # 找你妈，不找了<-咱还是回家吧

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
            print(html)
            html = {'content': html}
        print(333)

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
