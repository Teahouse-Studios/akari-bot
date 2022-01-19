'''
调用了其他API，但是已于CurseForge仓库对接。
'''
from core.utils import get_url
from bs4 import BeautifulSoup

search_piece_1 = 'https://files.xmdhs.top/curseforge/s?q='
search_piece_2 = '&type=1'
search_step_2 = 'https://files.xmdhs.top/curseforge/history?id='

def Chinese(string: str):
    for word in string:
        if u'\u4e00' <= word <= u'\u9fff':
            return True
    return False
async def curseforge(mod_name: str,ver: str):
    if Chinese(mod_name):
        return {'msg':'请不要输入中文，CurseForge暂不支持中文搜索。'}
    full_url = search_piece_1 + mod_name + search_piece_2
    html = await get_url(full_url)
    if html == '404 page not found':
        return {'msg':'未找到搜索结果。'}
    bs = BeautifulSoup(html,'html.parser')
    information = bs.body.div.div.a
    more_specific_html = str(information)
    id = more_specific_html[int(more_specific_html.find('id=')+3):int(more_specific_html.find('\" style='))]
    final_url = search_step_2 + id + '&ver=' + ver
    html_2 = await get_url(final_url)
    bs_2 = BeautifulSoup(html_2,'html.parser')
    try:
        results = bs_2.body.div.div.table.tbody.find_all('tr')
    except:
        return {'msg':'请不要尝试搜索不存在的Minecraft版本的Mod。'}
    information_2 = str(results[1])
    download_link = information_2[int(information_2.find("\"")+1):int(information_2.find("\" target="))]
    file_name = information_2[int(information_2.find("_blank\"")+8):int(information_2.find("</a>"))]
    if bool(information_2.find("Beta")) == True:
        status = "Release"
    if bool(information_2.find("Release")) == True:
        status = "Beta"
    dict = {"filename":file_name,"download_link":download_link,"status":status,'msg':'200 OK'}
    print(dict)
    return dict
    
