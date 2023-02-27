import secrets
from core.builtins.message import MessageSession
from core.component import on_regex

MAX_COIN_NUM = 20
FACE_UP_RATE = 4975  # n/10000
FACE_DOWN_RATE = 4975
COIN_DROP_PLACES = ["地上","桌子上","桌子底下","门口","窗户外","月球"]  # 硬币可能掉落的位置

dicergex = on_regex('coin_regex',
                  desc='打开后将在发送的聊天内容匹配以下信息时执行对应命令：\n'
                       '[丢/抛](n)[个/枚]硬币', developers=['Light-Beacon'])

@dicergex.handle(r"[丢|抛]([0-9]*)?[个|枚]?硬币")
async def _(message: MessageSession):
    groups = message.matched_msg.groups()
    count = groups[0] if groups[0] else '1'
    count = int(count)
    await message.finish(await flipCoins(count))

async def flipCoins(count:int):
    if count > MAX_COIN_NUM:
        return f"发生错误：你最多只能抛 {MAX_COIN_NUM} 个硬币"
    if FACE_UP_RATE + FACE_DOWN_RATE > 10000:
        raise OverflowError("硬币概率总和超过最大概率")
    faceUp = 0
    faceDown = 0
    stand = 0
    for i in range(count):
        randnum = secrets.randbelow(10000)
        if randnum < FACE_UP_RATE:
            faceUp += 1
        elif randnum < FACE_UP_RATE + FACE_DOWN_RATE:
            faceDown += 1
        else:
            stand += 1
    head = f"你投了 {count} 个硬币，"
    if count == 1:
        drop_place = COIN_DROP_PLACES[secrets.randbelow(len(COIN_DROP_PLACES))]
        head += f"它掉到了{drop_place}...\n"
        if faceUp:
            return head + "...是正面！"
        elif faceDown:
            return head + "...是反面！"
        else:
            return head + "...它...它立起来了！"
    else:
        if not (stand or faceDown):
            return "它们...\n...全是正面!"
        if not (stand or faceUp):
            return "它们...\n...全是反面!"
        if not (faceUp or faceDown):
            return "它们...\n...全都立起来了！？！？天哪！"
        output = "其中...\n"
        if faceUp:
            output += f"{faceUp}个是正面,"
        if faceDown:
            output += f"{faceDown}个是反面"
        if stand:
            output += f"...还有{stand}个立起来了！"
        return output