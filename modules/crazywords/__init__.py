import random

from core.builtins import Bot
from core.component import module

tarot = module('crazywords', desc='发电模块',
                   developers=['haoye_qwq'], alias='fadian')
@tarot.handle("<object> {发电}")
async def _(send: Bot.MessageSession):
    object_ = send.parsed_msg['<object>']
    template_ = [f"天哪，，，。。。我的{object_}……我的光般的{object_}。你是爱。你是卡密。是桥……你是才华！是月光（）是诗人，又温柔，又苦，意想不到地可爱，{object_}。{object_}。那么真诚！{object_}，那么真！又真（）意想不到地强大，又动人……我馋（）我永远热爱。我好爱，我泪洒太平洋……{object_}！我当场失控……我看一万遍，我狂呼乱叫，{object_}！我看一万遍。",
                 f"{object_} 您好，我是牙科医院的，这边为了检查您的牙齿健康，请您配合我的检查，首先朝我后颈脖子上咬一口🥵\n我是 {object_} 的狗😭有什么样的情有什么样的爱👫用什么样的爱还什么样的债💧我知道你的心里有些想不开🙅🏻‍♂️可是我的心里满满的全是爱❤️你回头看看我🤦🏻‍♂️不要再沉默🙇🏻‍♀️\n为什么会这么好看，我想不明白，我的所有脑细胞加在一起冥想一万亿年也无法参透为什么你这么好看的道理，你是造物主创造的皮格马利翁，就连神明也会为你们倾倒，你是黑夜也是黑夜里唯一一丝曙光，指引了我前进的方向，你是我活下去的动力，谢谢你，我命中注定的老婆\n{object_} 你不知道，我有三万种的情书可以写给你，可我不喜欢谈论情爱，我更喜欢你能按着我狂亲，否则我就要发疯一直疯到个明年了，可怜可怜我吧😭😭😭\n大家都填好志愿了吗？我的第一志愿是北大，但是我感觉我的分数可能不够，清华的话，可以冲一冲，最后一个保底的我选了{object_}的床，这个我应该是稳上的\n活着为了老婆😍💞死了为了老婆😇💞为老婆奋斗✊❣️为老婆痴狂🥰🌹为老婆流泪😭💛为老婆着迷🤩✨为老婆感动🥺💞爱老婆一辈子😍💖活着为了老婆😍💞死了为了老婆😇💞为老婆奋斗✊\n老婆瘾犯了 我好想老婆，好想老婆，无时无刻的想老婆 无止无尽的想你老婆 想完美的老婆 想崇高的老婆 想神圣的老婆 不想克制自己，上厕所的时候不敢想老婆，怕臭臭的空气亵渎了老婆🥵"]
    words_ = random.choice(template_) + "\n[90秒后撤回]"
    msg = await send.sendMessage(words_)
    await send.sleep(90)
    await msg.delete()


