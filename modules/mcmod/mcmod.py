from bs4 import BeautifulSoup
from config import Config
from core.utils import get_url

api = 'https://search.mcmod.cn/s?key='


async def mcmod(keyword: str):
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
        return f'{name}\n{url}\n{desc}'
    else:
        return '未找到结果。'
