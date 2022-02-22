from bs4 import BeautifulSoup

from config import Config
from core.elements import Url
from core.utils import get_url

api = 'https://search.mcmod.cn/s?filter=3&key='


async def moddetails(keyword: str):
    search_url = api + keyword
    webrender = Config('web_render')
    if webrender:
        search_url = webrender + 'source?url=' + search_url
    html = await get_url(search_url)
    print(html)
    bs = BeautifulSoup(html, 'html.parser')
    results = bs.find_all('div', class_='result-item')
    if results is not None:
        res = results[0]
        a = res.find('div', class_='head').find('a', recursive=False)
        name = a.text
        url = a['href']
        desc = res.find('div', class_='body').text
        return f'{name}\n{str(Url(url))}\n{desc}'
    else:
        return '未找到结果。'
