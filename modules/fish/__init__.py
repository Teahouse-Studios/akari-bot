import asyncio
import os
import random
import re
import traceback
from datetime import datetime

from PIL import Image as PILImage
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt

from core.builtins import Bot
from core.builtins import Image, Plain
from core.component import module
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.cooldown import CoolDown
from core.utils.http import get_url, download_to_cache
from core.utils.text import remove_prefix
from modules.core.su_utils import gained_petal

fish = module('fish',
              desc='{fish.help.desc}', developers=['OasisAkari'])
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


async def finish_fish(msg: Bot.MessageSession):
    play_state[msg.target.target_id]['active'] = False
    if msg.target.target_from != 'TEST|Console':
        qc = CoolDown('fish', msg)
        qc.reset()
    if play_state[msg.target.target_id]['hooked']:
        fish_name_key = 'fish.message.type.' + play_state[msg.target.target_id]['fish_name']
        fish_name = msg.locale.t(fish_name_key, fallback_failed_prompt=False)
        if fish_name == fish_name_key:
            fish_name = play_state[msg.target.target_id]['fish_name']
        fish_words_key = 'fish.message.fished.' + play_state[msg.target.target_id]['fish_name']
        fish_words = msg.locale.t(fish_words_key, fallback_failed_prompt=False)
        if fish_words == fish_words_key:
            fish_words = msg.locale.t('fish.message.fished', name=fish_name)
        text = f'{fish_words}\n' + \
               f'体型：{msg.locale.t("fish.message.size." + play_state[msg.target.target_id]["fish_type"])}'
        if play_state[msg.target.target_id]['hooked_time'] < 2:
            if g := gained_petal(msg, 1):
                text += '\n' + g
        await msg.finish(text, quote=False)
    else:
        await msg.finish('你收回了鱼竿，什么都没有钓到。', quote=False)


@fish.command('{{fish.help}}')
async def fish(msg: Bot.MessageSession):
    if msg.target.target_from != 'TEST|Console':
        qc = CoolDown('fish', msg)
        c = qc.check(60)
        if c != 0:
            await msg.finish(msg.locale.t('message.cooldown', time=int(c), cd_time='60'))
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        return await finish_fish(msg)
    play_state.update({msg.target.target_id: {'active': True, 'hooked': False}})

    async def ans(msg: Bot.MessageSession):  # 定义回答函数的功能
        wait = await msg.wait_anyone()  # 等待对象内的任意人回答
        if play_state[msg.target.target_id]['active']:  # 检查对象是否为活跃状态
            if (wait_text := wait.as_display(text_only=True)) in ['收', '收杆']:
                return await finish_fish(msg)
            else:
                return ans(msg)

    async def generate_fish(msg: Bot.MessageSession):
        fish_type = random.choice(list(fish_list.keys()))
        fish_name = random.choice(fish_list[fish_type])
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
                            await msg.send_message(msg.locale.t(f"fish.message.escaped.{repeat_state}.{random.randint(1, 3)}"),
                                                   quote=False)
                            play_state[msg.target.target_id]['hooked'] = False
                            hooked_time = await generate_fish(msg)
                            wait_time = random.randint(5, 30)
                            wait_repeat = 0
                            hook_repeat = 0
                    else:
                        if hooked_time % 1 == 0:
                            await msg.send_message(msg.locale.t(f"fish.message.hooked.{repeat_state}.{random.randint(1, 3)}"),
                                                   quote=False)
                            hook_repeat += 1
                        play_state[msg.target.target_id]['hooked'] = True
                        hooked_time -= 0.25
                else:
                    if wait_time % 5 == 0:
                        wait_repeat += 1
                        await msg.send_message(f'.' * wait_repeat, quote=False)
                    wait_time -= 0.25

                await asyncio.sleep(0.25)

                await timer(start, wait_time, hooked_time, wait_repeat, hook_repeat)  # 重新调用计时器函数

    await msg.send_message(msg.locale.t('fish.message.start'))
    await asyncio.gather(ans(msg), timer(datetime.now().timestamp(), wait_time, hooked_time))
