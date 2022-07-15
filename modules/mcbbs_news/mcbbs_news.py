from bs4 import BeautifulSoup

from core.elements import Url
from core.utils import get_url


async def get_news():
    titles = []
    authors = []
    publish_time = []
    kinds = []
    links = []
    mcbbs_source_code = await get_url('https://www.mcbbs.net/forum-news-1.html')
    BeautifulSoupObject = BeautifulSoup(mcbbs_source_code, "html.parser")
    information = BeautifulSoupObject.find_all("tbody")
    for i in information:
        if i.get("id") is None:
            i.decompose()
            continue
        if str(i.get("id")).find("separatorline") != -1:
            i.decompose()
            continue
        if str(i.get("id")).find("stick") != -1:
            i.decompose()
            continue
    available_information = BeautifulSoupObject.find_all("tbody")

    # 先摆烂，谁愿意合并，请便吧（  ——HornCopper
    for i in available_information:
        x = BeautifulSoup(str(i), "html.parser")
        td = x.find_all("td")
        try:
            author = td[1].cite.a.string
        except:
            author = td[1].cite.string
        authors.append(author)

    for i in available_information:
        x = BeautifulSoup(str(i), "html.parser")
        em = x.find_all("em")
        kinds.append(em[0].a.string)

    for i in available_information:
        x = BeautifulSoup(str(i), "html.parser")
        em = x.find_all("em")
        try:
            time = em[1].span.span.string
        except:
            time = em[1].span.string
        publish_time.append(time)

    for i in available_information:
        x = BeautifulSoup(str(i), "html.parser")
        a = x.find_all("a")
        titles.append(a[4].string)

    for i in available_information:
        x = BeautifulSoup(str(i), "html.parser")
        link = "https://www.mcbbs.net/" + x.tr.td.a["href"]
        links.append(Url(link))

    return {"titles": titles, "time": publish_time, "authors": authors, "kinds": kinds, "links": links}
