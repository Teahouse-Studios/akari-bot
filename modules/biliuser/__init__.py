from core.elements import MessageSession
import httpx
import asyncio
import re
import json
from core.elements.others import ErrorMessage
from core.utils import 
from aiocqhttp import MessageSegment

biliapi = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history?host_uid="

async def bilibili_user_infomation_getter(uid: str):
    final_url = biliapi + uid
    first_json = await get_url(final_url)
    second_json = json.loads(first_json)
    try:
        fourth_json = second_json["data"]["cards"]
    except:
        final_json = {"name":"null","sign":"null","avatar":"null","vip_flag":"null","vip":"null"}
        result = json.dumps(final_json)
        return result
    for fifth_json in fourth_json:
        sixth_json = fifth_json["desc"]["user_profile"]
        seventh_json = sixth_json["info"]
        name = str(seventh_json["uname"])
        sign = str(sixth_json["sign"])
        avatar_link = re.sub(r": ",":",str(seventh_json["face"]))
        if str(sixth_json["vip"]["vipType"]) == "1" or "2":
            vip = sixth_json["vip"]["label"]["text"]
            vip_flag = 1
        else:
            vip_flag = 0
    if vip_flag:
        final_json = {"name":name,"sign":sign,"avatar":avatar_link,"vip_flag":vip_flag,"vip":vip}
    else:
        final_json = {"name":name,"sign":sign,"avatar":avatar_link,"vip_flag":vip_flag}
    result = json.dumps(final_json)
    return result

async def handle_uid(uid):
    final_information = await final(uid)
    information = json.loads(await bilibili_user_infomation_getter(uid))
    if str(information["name"]) == "null":
        await biliuser.send("此用户不存在，请检查输入！")
    else:
        img_url = str(information["avatar"])
        await biliuser.send(final_information+MessageSegment.image(img_url))
async def final(uid):
    information = json.loads(await bilibili_user_infomation_getter(uid))
    print(information)
    name = str(information["name"])
    sign = str(information["sign"])
    vip_flag = bool(information["vip_flag"])
    if str(information["vip"]) == '':
        message = "用户名："+name+"\n简介："+sign+"\nUID："+uid+"\n用户主页："+"https://space.bilibili.com/"+uid+"\n"
    else:
        vip = str(information["vip"])
        message = "用户名："+name+"\n简介："+sign+"\nUID："+uid+"\n用户主页："+"https://space.bilibili.com/"+uid+"\n"+"此用户是"+vip+"！"
    return message
