import datetime

from bs4 import BeautifulSoup

from config import CFG
from core.builtins import Url
from core.logger import Logger
from core.utils.http import get_url


async def news(msg):
    api = 'https://www.mcbbs.net/forum-news-1.html'
    webrender = CFG.get_url('web_render')
    if webrender:
        api = webrender + 'source?url=' + api
    html = await get_url(api, 200)
    Logger.debug(html)
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
            category = i.select_one('tr > th > em > a').get_text()
            author = i.select_one(
                'tr > td.by > cite > a').get_text()
            time = i.select_one('tr > td.by > em').get_text()
            if time.find('-') != -1:
                time = time.split('-')
                time_class = datetime.date(
                    int(time[0]), int(time[1]), int(time[2]))
                delta = datetime.date.today() - time_class
                time = str(delta.days) + ' 天前'

            title = a.get_text()
            url = Url('https://www.mcbbs.net/' + a.get('href'))
            res += [{'count': len(res) + 1, 'title': title, 'url': url,
                     'author': author, 'time': time, 'category': category}]
        return res
    else:
        return None
