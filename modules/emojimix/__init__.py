import os
from typing import List, Optional, Tuple

import emoji
import orjson as json

from core.builtins import Bot, MessageChain, Image, I18NContext, Plain
from core.component import module
from core.constants.path import assets_path
from core.logger import Logger
from core.utils.random import Random

data_path = os.path.join(assets_path, "modules", "emojimix", "emoji_data.json")
API = "https://www.gstatic.com/android/keyboard/emojikitchen"


class EmojimixGenerator:
    def __init__(self):
        with open(data_path, "rb") as f:
            data = json.loads(f.read())
        self.known_supported_emoji: List[str] = data["knownSupportedEmoji"]
        self.data: dict = data["data"]
        self.date_mapping: dict = dict(enumerate(data["date"]))

    @staticmethod
    def str2emoji(emoji_str):
        parts = emoji_str.split("-")
        emoji_chars = [chr(int(part, 16)) for part in parts]
        emoji = "".join(emoji_chars)
        return emoji

    @staticmethod
    def make_emoji_tuple(emoji1: str, emoji2: str) -> Tuple[str, str]:
        emoji_code1 = "-".join(f"{ord(char):x}" for char in emoji1)
        emoji_code2 = "-".join(f"{ord(char):x}" for char in emoji2)
        return (emoji_code1, emoji_code2)

    def random_choice_emoji(self, emoji: Optional[str] = None) -> Tuple[str, str]:
        if emoji:
            emoji_code = "-".join(f"{ord(char):x}" for char in emoji)
            emoji_combo_list = []
            for key in self.data:
                if emoji_code in key:
                    emoji_combo_list.append(key)
            combo = Random.choice(emoji_combo_list)
        else:
            combo = Random.choice(list(self.data.keys()))
        combo = tuple(i.strip() for i in combo[1:-1].split(","))
        return combo

    def check_supported(self, emoji_tuple: Tuple[str, str]) -> List[str]:
        unsupported_emojis: List[str] = []
        checked: set = set()
        for emoji_ in emoji_tuple:
            if emoji_ not in self.known_supported_emoji and emoji_ not in checked:
                emoji_symbol = "".join(chr(int(segment, 16)) for segment in emoji_.split("-"))
                unsupported_emojis.append(emoji_symbol)
                checked.add(emoji_)
        return unsupported_emojis

    def mix_emoji(self, emoji_tuple: Tuple[str, str]) -> Optional[str]:
        str_tuple_1 = f"({emoji_tuple[0]}, {emoji_tuple[1]})"
        str_tuple_2 = f"({emoji_tuple[1]}, {emoji_tuple[0]})"

        if str_tuple_1 in self.data:
            date_index = self.data[str_tuple_1]
            date = self.date_mapping[date_index]
            left_emoji = emoji_tuple[0]
            right_emoji = emoji_tuple[1]
        elif str_tuple_2 in self.data:
            date_index = self.data[str_tuple_2]
            date = self.date_mapping[date_index]
            left_emoji = emoji_tuple[1]
            right_emoji = emoji_tuple[0]
        else:
            return None

        left_code_point = "-".join(f"u{segment}" for segment in left_emoji.split("-"))
        right_code_point = "-".join(f"u{segment}" for segment in right_emoji.split("-"))
        url = f"{API}/{date}/{left_code_point}/{left_code_point}_{right_code_point}.png"
        return url

    def list_supported_emojis(self, emoji: Optional[str] = None) -> Optional[List[str]]:
        supported_combinations: List[str] = []

        if emoji:
            emoji_symbol = emoji

            emoji_code = "-".join(f"{ord(char):x}" for char in emoji_symbol)
            if emoji_code not in self.known_supported_emoji:
                return None

            for key in self.data:
                if emoji_code in key:
                    pair = key.replace("(", "").replace(")", "").split(", ")
                    pair = [p.strip() for p in pair]
                    if pair[0] == emoji_code:
                        pair_emoji = "".join(chr(int(segment, 16)) for segment in pair[1].split("-"))
                        supported_combinations.append(pair_emoji)
                    elif pair[1] == emoji_code:
                        pair_emoji = "".join(chr(int(segment, 16)) for segment in pair[0].split("-"))
                        supported_combinations.append(pair_emoji)
        else:
            for emoji_code in self.known_supported_emoji:
                emoji_char = "".join(chr(int(segment, 16)) for segment in emoji_code.split("-"))
                supported_combinations.append(emoji_char)

        return sorted(supported_combinations, key=str)


mixer = EmojimixGenerator()


emojimix = module("emojimix", developers=["DoroWolf"], doc=True)


@emojimix.command()
async def _(msg: Bot.MessageSession):
    combo = mixer.random_choice_emoji()
    Logger.debug(str(combo))
    result = mixer.mix_emoji(combo)
    Logger.debug(result)
    await msg.finish([Plain(f"{mixer.str2emoji(combo[0])}+{mixer.str2emoji(combo[1])}"), Image(result)])


@emojimix.command("<emoji1> [<emoji2>] {{I18N:emojimix.help}}")
async def _(msg: Bot.MessageSession, emoji1: str, emoji2: str = None):
    # 兼容性处理
    if "+" in emoji1:
        emojis = emoji1.split("+", 1)
        emoji1 = emojis[0]
        emoji2 = emojis[1] if len(emojis) > 1 else None
        if emoji2 and not emoji1:
            emoji1, emoji2 = emoji2, emoji1
    elif emoji1 and not emoji2:
        emojis = [item['emoji'] for item in emoji.emoji_list(emoji1)]
        emoji1 = emojis[0]
        emoji2 = emojis[1] if len(emojis) > 1 else None

    if not emoji.is_emoji(emoji1):
        await msg.finish(I18NContext("emojimix.message.invalid"))
    if emoji2:
        if not emoji.is_emoji(emoji2):
            await msg.finish(I18NContext("emojimix.message.invalid"))
        combo = mixer.make_emoji_tuple(emoji1, emoji2)
        Logger.debug(str(combo))
        unsupported_emojis = mixer.check_supported(combo)
        if unsupported_emojis:
            await msg.finish(I18NContext("emojimix.message.unsupported", emoji="{I18N:message.delimiter}".join(unsupported_emojis)))
    else:
        emoji_code1 = "-".join(f"{ord(char):x}" for char in emoji1)
        if emoji_code1 not in mixer.known_supported_emoji:
            await msg.finish(I18NContext("emojimix.message.unsupported", emoji=emoji1))
        combo = mixer.random_choice_emoji(emoji1)
        Logger.debug(str(combo))

    result = mixer.mix_emoji(combo)
    if result:
        await msg.finish([Plain(f"{mixer.str2emoji(combo[0])}+{mixer.str2emoji(combo[1])}"), Image(result)])
    else:
        await msg.finish(I18NContext("emojimix.message.not_found"))


@emojimix.command("list [<emoji>] {{I18N:emojimix.help.list}}")
async def _(msg: Bot.MessageSession, emoji: str = None):
    supported_emojis = mixer.list_supported_emojis(emoji)
    if emoji:
        if supported_emojis:
            send_msgs = MessageChain(I18NContext("emojimix.message.combine_supported", emoji=emoji))
            if msg.target.client_name == "Discord":
                send_msgs += MessageChain([Plain("".join(supported_emojis[i:i + 200]))
                                           for i in range(0, len(supported_emojis), 200)])
            else:
                send_msgs.append(Plain("".join(supported_emojis)))
            await msg.finish(send_msgs)
        else:
            await msg.finish(I18NContext("emojimix.message.unsupported", emoji=emoji))
    else:
        send_msgs = MessageChain(I18NContext("emojimix.message.all_supported"))
        if supported_emojis:
            if msg.target.client_name == "Discord":
                send_msgs += MessageChain([Plain("".join(supported_emojis[i:i + 200]))
                                           for i in range(0, len(supported_emojis), 200)])
            else:
                send_msgs.append(Plain("".join(supported_emojis)))
        await msg.finish(send_msgs)
