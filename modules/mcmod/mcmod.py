from urllib.parse import quote

from bs4 import BeautifulSoup

from core.builtins.message.internal import I18NContext, Url, Plain
from core.utils.web_render import web_render, SourceOptions

api = "https://search.mcmod.cn/s?key="
api_details = "https://search.mcmod.cn/s?filter=3&key="


async def mcmod(keyword: str, detail: bool = False):
    endpoint = api_details if detail else api
    search_url = endpoint + quote(keyword)
    html = await web_render.source(SourceOptions(url=search_url))
    if html:
        bs = BeautifulSoup(html, "html.parser")
        results = bs.find_all("div", class_="result-item")
        if results:
            res = results[0]
            a = res.find("div", class_="head").find("a", recursive=False)
            name = a.text
            url = a["href"]
            desc = res.find("div", class_="body").text
            return [Plain(name), Url(url, use_mm=False), Plain(desc)]
    return I18NContext("mcmod.message.not_found")
