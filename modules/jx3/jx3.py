import json
from core.utils import get_url
async def server_status(server_name):
    full_link = "https://www.jx3api.com/app/check?server="+server_name
    info = json.loads(await get_url(full_link))
    try:
        all_servers = info["data"]
        if str(type(all_servers)).find("list") != -1:
            return "服务器名输入错误。"
    except:
        pass
    status = info["data"]["status"]
    if status == 1:
        return f"{server_name}服务器状态正常。"
    elif status == 0:
        return f"{server_name}服务器维护中。"

async def horse_flush_place(horse_name):
    def template(place, last_update):
        return f"刷新地点：{place}\n上次更新：{last_update}\n"
    full_link = "https://www.jx3api.com/app/horse?name="+horse_name
    info = json.loads(await get_url(full_link))
    if info["code"] == 401:
        return "未找到对应马匹。"
    msg = ""
    maps = info["data"]["data"]
    if len(maps) <1:
        return "该马匹没有刷新地点。"
    for i in maps:
        msg = msg + template(i["map"],i["datetime"])
    return msg
