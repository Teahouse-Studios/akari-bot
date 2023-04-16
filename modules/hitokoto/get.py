import requests
import json

type_to_name = {'a':'动画', 'b':'漫画', 'c':'游戏', 'd':'文学', 
                'e':'原创', 'f':'来自网络', 'g':'其他', 'h':'影视',
                'i':'诗词', 'j':'网易云', 'k':'哲学', 'l':'抖机灵'}

async def get_hitokoto():
    url = 'https://v1.hitokoto.cn/?encode=json'
    responce = requests.get(url)
    get_json = responce.json()
    if get_json['from_who'] != None:
        send_msg = '一言 #' + str(get_json['id']) + '\n\n' + get_json['hitokoto'] + '\n\n来源：' + type_to_name[get_json['type']] + '——' + get_json['from'] + ' ' + get_json['from_who']
    else:
        send_msg = '一言 #' + str(get_json['id']) + '\n\n' + get_json['hitokoto'] + '\n\n来源：' + type_to_name[get_json['type']] + '——' + get_json['from'] + ' 未知'
    return (send_msg)