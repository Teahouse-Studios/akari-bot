from bs4 import BeautifulSoup
from config import Config
from core.elements import Url
from core.utils import get_url


async def news():
    api = 'https://www.mcbbs.net/forum-news-1.html'
    webrender = Config('web_render')
    if webrender:
        api = webrender + 'source?url=' + api
    html = await get_url(api)
    print(html)
    bs = BeautifulSoup(html, 'html.parser')
    results = bs.select('#threadlisttableid > tbody[id^="normalthread_"]')
    res = []
    if results is not None:
        for i in results:
            if len(res) == 5:
                break
            a = i.select_one('a.s.xst')
            if not a.has_attr('style'):
                continue
            title = a.get_text()
            url = Url('https://www.mcbbs.net/' + a.get('href'))
            res += [{'count': len(res) + 1, 'title': title, 'url': url}]
        return res
    else:
        return None
