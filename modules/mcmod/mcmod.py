from urllib.parse import quote

from bs4 import BeautifulSoup

from config import Config
from core.elements import Url
from core.utils import get_url

api = 'https://search.mcmod.cn/s?key='
api_details = 'https://search.mcmod.cn/s?filter=3&key='


async def mcmod(keyword: str, detail: bool = False):
    endpoint = api_details if detail else api
    search_url = endpoint + quote(keyword)
    webrender = Config('web_render')
    if not webrender:
        return
    search_url = webrender + 'source?url=' + quote(search_url)
    html = await get_url(search_url, 200)
    print(html)
    bs = BeautifulSoup(html, 'html.parser')
    results = bs.find_all('div', class_='result-item')
    if results:
        res = results[0]
        a = res.find('div', class_='head').find('a', recursive=False)
        name = a.text
        url = a['href']
        desc = res.find('div', class_='body').text
        return f'{name}\n{str(Url(url))}\n{desc}'
    else:
        return '未找到结果。'
