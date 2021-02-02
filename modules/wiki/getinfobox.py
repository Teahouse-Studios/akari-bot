import asyncio
import json
import os
import re
import traceback
import uuid

import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from config import config
from modules.wiki.helper import get_url

config_path = os.path.abspath('./config/config.cfg')

try:
    if config_path:
        infobox_render = config(config_path, 'infobox_render')
except:
    infobox_render = None


async def get_infobox_pic(link, pagelink):
    try:
        print('hello')
        link = re.sub(r'(?:w/|)api.php', '', link)
        print(link)
        print(pagelink)
        try:
            html = await get_url(pagelink, 'text')
            print(html)
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
        find_infobox = soup.find(class_='notaninfobox')
        if find_infobox is None:
            find_infobox = soup.find(class_='infobox')
            if find_infobox is None:
                find_infobox = soup.find(class_='portable-infobox')
                if find_infobox is None:
                    find_infobox = soup.find(class_='tpl-infobox')
                    if find_infobox is None:
                        return False#找你妈，不找了


        if infobox_render is None:
            open_file = open(url, 'a', encoding='utf-8')
        else:
            html_list = []

        for x in soup.find_all(rel='stylesheet'):
            y = str(x.get('href'))
            z = re.sub('^/load.php', f'{link}load.php', y)
            if infobox_render is None:
                open_file.write(f'<link href="{z}" rel="stylesheet"/>\n')
            else:
                html_list.append(f'<link href="{z}" rel="stylesheet"/>\n')

        replace_link = re.sub(r'href=\"/(.*)\"', 'href=\"' + link + '\\1\"', str(find_infobox), re.M)
        replace_link = re.sub(r'\(/(media/)', '(' + link + '\\1', replace_link, re.M)

        if infobox_render is None:
            open_file.write(str(replace_link))
            open_file.close()
        else:
            html_list.append(str(replace_link))
            html = {'content': '\n'.join(html_list)}
            print(html)
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
