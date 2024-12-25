import orjson as json
import random
from core.builtins import Bot, Plain, Image
from core.component import module
from core.extra import reverse_img

tarot = module('tarot', desc='塔罗牌模块(移植自https://github.com/LaoLittle/SimpleTarot)',
                   developers=['haoye_qwq'], alias=['塔罗牌', '今日塔罗'])


@tarot.handle('{获取随机塔罗}')
async def _(send: Bot.MessageSession):
    with open('./assets/tarot/tarot_cards.json', 'r', encoding='utf8') as tdata:
        taro_data = json.loads(tdata.read())
    pre_taro = random.choice(taro_data)
    facing = ["positive", "negative"]
    selected_facing = random.choice(facing)
    taro_text = None
    card = None
    if selected_facing == "positive":
        taro_text = pre_taro["name"] + '\n正位\n' + pre_taro["positive"]
        card = pre_taro["imageName"]
    elif selected_facing == "negative":
        taro_text = pre_taro["name"] + '\n逆位\n' + pre_taro["negative"]
        card = reverse_img(pre_taro["imageName"])
    msg1 = await send.send_message(Plain(taro_text+'\n[60秒后撤回]'),quote=False)
    msg2 = await send.send_message(Image(card),quote=False)
    await send.sleep(60)
    await msg1.delete()
    await msg2.delete()
