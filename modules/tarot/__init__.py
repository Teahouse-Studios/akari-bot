import ujson as json
import random
import time
from core.builtins import Bot, Plain, Image
from core.component import module
from core.extra import reverse_img

tarot = module('tarot', desc='塔罗牌模块(移植自https://github.com/LaoLittle/SimpleTarot)',
                   developers=['haoye_qwq'], alias=['塔罗牌', '今日塔罗'])


@tarot.handle('{获取随机塔罗}')
async def _(send: Bot.MessageSession):
    with open('./assets/TarotData.json', 'r', encoding='utf8') as tdata:
        taro_data = json.load(tdata)
    preprocessed_taro_data = random.choice(taro_data)
    facing = ["positive", "negative"]
    selected_facing = random.choice(facing)
    if selected_facing == "positive":
        plain_ = preprocessed_taro_data["name"] + '\n正位\n' + preprocessed_taro_data["positive"]
        img_ = preprocessed_taro_data["imageName"]
    elif selected_facing == "negative":
        plain_ = preprocessed_taro_data["name"] + '\n逆位\n' + preprocessed_taro_data["negative"]
        img_ = reverse_img(preprocessed_taro_data["imageName"])
    msg = await send.sendMessage([Plain(plain_+'\n[30秒后撤回]'), Image(img_)])
    await send.sleep(30)
    await msg.delete()
