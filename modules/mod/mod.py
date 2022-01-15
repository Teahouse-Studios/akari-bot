import re
from bs4 import BeautifulSoup
from core.utils import get_url

search_link = "https://search.mcmod.cn/s?key="


async def mcmod(keyword: str):
    full_requests_link = search_link + keyword
    html = await get_url(full_requests_link)
    useful_information = html[int(html.find("<div class=\"search-result-list\">")):int(html.find("<footer>")-1)]+">"
    bshtml = BeautifulSoup(useful_information,'html.parser')
    more_useful_information = bshtml.div.div.find_all('div')
    str0_1 = str(more_useful_information[2])
    potato = str0_1[:20]
    if potato.find("body"):
        desc = re.sub(r"\[(.+?)\]","",str0_1[int(str0_1.find("<div class=\"body\">")+18):int(str0_1.find("</div>"))])
        str0_2 = bshtml.div.div.find_all('a')
        str3 = str(str0_2[2])
        link = str3[int(str3.find("\"")+1):int(str3.find(" target")-1)]
        return f"{link}\n{desc}"
    else:
        return f"Mod不存在，检索失败"
