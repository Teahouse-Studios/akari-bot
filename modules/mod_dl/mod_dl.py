'''
调用了其他API，但是已于CurseForge仓库对接。
'''
import traceback

from bs4 import BeautifulSoup

from core.utils import get_url

search_piece_1 = 'https://files.xmdhs.com/curseforge/s?q='
search_piece_2 = '&type=1'
search_step_2 = 'https://files.xmdhs.com/curseforge/history?id='


def Chinese(string: str):
    for word in string:
        if u'\u4e00' <= word <= u'\u9fff':
            return True
    return False


async def curseforge(mod_name: str, ver: str):
    if Chinese(mod_name):
        return {'msg': 'CurseForge暂不支持中文搜索。', 'success': False}
    full_url = search_piece_1 + mod_name + search_piece_2
    html = await get_url(full_url)
    bs = BeautifulSoup(html, 'html.parser')
    try:
        information = bs.body.div.div.a
        mod_title = information.find('h3').text
    except Exception:
        return {'msg': '未搜索到该Mod。', 'success': False}
    more_specific_html = str(information)
    id = more_specific_html[int(more_specific_html.find('id=') + 3):int(more_specific_html.find('\" style='))]
    final_url = search_step_2 + id + '&ver=' + ver
    html_2 = await get_url(final_url)
    bs_2 = BeautifulSoup(html_2, 'html.parser')
    try:
        results = bs_2.body.div.find_all('tr')
        information_2 = str(results[1])
    except Exception:
        traceback.print_exc()
        return {'msg': f'此{mod_title}没有{ver}的版本。', 'success': False}
    download_link = information_2[int(information_2.find("\"") + 1):int(information_2.find("\" target="))]
    file_name = information_2[int(information_2.find("_blank\"") + 8):int(information_2.find("</a>"))]
    status = '???'
    if bool(information_2.find("Beta")):
        status = "Release"
    if bool(information_2.find("Release")):
        status = "Beta"
    return {"filename": file_name, "download_link": download_link, "status": status, "success": True}
