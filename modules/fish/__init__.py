import asyncio
import random
from datetime import datetime

from config import Config
from core.builtins import Bot
from core.component import module
from core.logger import Logger
from core.petal import gained_petal, lost_petal
from core.utils.cooldown import CoolDown

fish = module('fish',
              desc='{fish.help.desc}',
              alias={"retract": "fish retract"}, developers=['OasisAkari'])
play_state = {}  # 创建一个空字典用于存放游戏状态

fish_list = {
    'tiny': ['bitterling', 'pale-chub', 'goldfish', 'pop-eyed-goldfish', 'killifish', 'tadpole', 'guppy', 'nibble-fish',
             'rainbow-fish', 'sea-butterfly', 'sea-horse'],
    'small': ['crucian-carp', 'ranchu-goldfish', 'frog', 'loach', 'bluegill',
              'pond-smelt', 'angel-fish', 'betta', 'piranha', 'butterfly-fish', 'anchovy',
              'horse-mackerel',
              'barrel-eye'],
    'medium': ['dace', 'yellow-perch', 'tilapia', 'cherry-salmon', 'char', 'golden-trout',
               'zebra-turkeyfish',
               'blow-fish', 'barred-knifejaw', 'squid'],
    'large': ['carp', 'koi', 'soft-shelled-turtle', 'giant-snakehead', 'black-bass',
              'saddled-bichir', 'red-snapper', 'football-fish'],
    'very-large': ['pike', 'string-fish',
                   'dorado', 'gar', 'sea-bass', 'giant-trevally', 'mahi-mahi', 'ray'],
    'long-thin': ['moray-eel', 'ribbon-eel'],
    'very-large-finned': ['saw-shark', 'hammerhead-shark', 'great-white-shark', 'whale-shark'],
    'huge': ['sturgeon', 'oar-fish', 'coelacanth', 'tuna', 'blue-marlin'],
}

fish_list_by_name = {x: y for y in fish_list for x in fish_list[y]}


async def finish_fish(msg: Bot.MessageSession):
    play_state[msg.target.target_id]['active'] = False
    if msg.target.target_from != 'TEST|Console':
        qc = CoolDown('fish', msg, all=True)
        qc.reset()
    if play_state[msg.target.target_id]['hooked']:
        rand_result = random.randint(1, 100)
        if rand_result < 98:
            fish_name_key = 'fish.message.type.' + play_state[msg.target.target_id]['fish_name']
            fish_name = msg.locale.t(fish_name_key, fallback_failed_prompt=False)
            if fish_name == fish_name_key:
                fish_name = play_state[msg.target.target_id]['fish_name']
            fish_words_key = 'fish.message.fished.' + play_state[msg.target.target_id]['fish_name']
            fish_words = msg.locale.t(fish_words_key, fallback_failed_prompt=False)
            if fish_words == fish_words_key:
                fish_words = msg.locale.t('fish.message.fished', name=fish_name)
            text = f'{fish_words}\n' + \
                   (f'{msg.locale.t("fish.message.size")}'
                    f'{msg.locale.t("fish.message.size." + play_state[msg.target.target_id]["fish_type"])}')
            if play_state[msg.target.target_id]['hooked_time'] < 2:
                if g := await gained_petal(msg, 1):
                    text += '\n' + g
            await msg.finish(text, quote=False)
        else:
            send = msg.locale.t('fish.message.failed.' + str(random.randint(1, 3)))
            if g := await lost_petal(msg, 1):
                send += '\n' + g
            await msg.finish(send, quote=False)
    else:
        await msg.finish(msg.locale.t("fish.message.fished.nothing"), quote=False)


@fish.command('{{fish.help}}')
async def _(msg: Bot.MessageSession):
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        return await finish_fish(msg)
    if msg.target.target_from != 'TEST|Console':
        qc = CoolDown('fish', msg, all=True)
        c = qc.check(30)
        if c != 0:
            await msg.finish(msg.locale.t('message.cooldown', time=int(c), cd_time=30))
    play_state.update({msg.target.target_id: {'active': True, 'hooked': False}})

    async def generate_fish(msg: Bot.MessageSession):
        fish_name = random.choice(list(fish_list_by_name.keys()))
        fish_type = fish_list_by_name[fish_name]
        play_state[msg.target.target_id]['fish_type'] = fish_type
        play_state[msg.target.target_id]['fish_name'] = fish_name
        hooked_time_chance = random.randint(1, 100)
        if 0 <= hooked_time_chance < 70:
            hooked_time = random.randint(1, 2)
        elif 70 <= hooked_time_chance < 80:
            hooked_time = random.randint(3, 4)
        elif 80 <= hooked_time_chance < 90:
            hooked_time = random.randint(5, 6)
        elif 90 <= hooked_time_chance < 95:
            hooked_time = random.randint(7, 8)
        elif 95 <= hooked_time_chance < 98:
            hooked_time = random.randint(9, 10)
        else:
            hooked_time = random.randint(11, 30)
        Logger.debug(f'fish_type: {fish_type}, fish_name: {fish_name}, hooked_time: {hooked_time}')
        play_state[msg.target.target_id]['hooked_time'] = hooked_time
        return hooked_time

    hooked_time = await generate_fish(msg)
    wait_time = random.randint(5, 30)

    async def timer(start, wait_time=0, hooked_time=0, wait_repeat=0, hook_repeat=0):  # 计时器函数
        if play_state[msg.target.target_id]['active']:  # 检查对象是否为活跃状态
            if datetime.now().timestamp() - start > 120:  # 如果超过2分钟
                await msg.send_message(msg.locale.t('fish.message.timeout'), quote=False)
                play_state[msg.target.target_id]['active'] = False
            else:  # 如果未超时
                if hook_repeat < 3:
                    repeat_state = 'green'
                elif hook_repeat < 6:
                    repeat_state = 'blue'
                elif hook_repeat < 9:
                    repeat_state = 'yellow'
                else:
                    repeat_state = 'red'
                if wait_time <= 0:
                    if hooked_time <= 0:
                        if play_state[msg.target.target_id]['active']:
                            play_state[msg.target.target_id]['hooked'] = False
                            await msg.send_message(msg.locale.t(f"fish.message.escaped.{repeat_state}.{random.randint(1, 3)}"),
                                                   quote=False)
                            hooked_time = await generate_fish(msg)
                            wait_time = random.randint(5, 30)
                            wait_repeat = 0
                            hook_repeat = 0
                    else:
                        play_state[msg.target.target_id]['hooked'] = True
                        if hooked_time % 1 == 0:
                            await msg.send_message(msg.locale.t(f"fish.message.hooked.{repeat_state}.{random.randint(1, 3)}"),
                                                   quote=False)
                            hook_repeat += 1
                        hooked_time -= 0.25
                else:
                    if wait_time % 10 == 0:
                        wait_repeat += 1
                        await msg.send_message(f'.' * wait_repeat, quote=False)
                    wait_time -= 0.25

                await msg.sleep(0.25)

                await timer(start, wait_time, hooked_time, wait_repeat, hook_repeat)  # 重新调用计时器函数

    await msg.send_message(msg.locale.t('fish.message.start', prefix=msg.prefixes[0]))
    Bot.ExecutionLockList.remove(msg)
    await asyncio.create_task(timer(datetime.now().timestamp(), wait_time, hooked_time))


@fish.handle('retract {{fish.retract.help}}')
@fish.regex(r'^(?:收杆|收)$')
async def _(msg: Bot.MessageSession):
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        await finish_fish(msg)
    else:
        rand_result = random.randint(1, 100)
        if Config('enable_get_petal') or rand_result < 90:
            send = msg.locale.t('fish.message.not_started.1', prefix=msg.prefixes[0])
        else:
            send = msg.locale.t('fish.message.not_started.2')
            if g := (g_msg := await lost_petal(msg, 1)):
                send += '\n' + g
        await msg.finish(send)
