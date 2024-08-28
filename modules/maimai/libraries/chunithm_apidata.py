import os
import traceback
from typing import Optional

import ujson as json

from config import Config
from core.builtins import Bot, Image, MessageChain, Plain
from core.logger import Logger
from core.utils.http import post_url
from .chunithm_music import Music

cache_dir = os.path.abspath(Config('cache_path', './cache/'))
assets_dir = os.path.abspath('./assets/maimai/')


async def get_info(music: Music, *details) -> MessageChain:
    info = [Plain(f"{music.id} - {music.title}")]
    cover_dir = os.path.join(assets_dir, "static", "chu", "cover")
    cover_path = os.path.join(cover_dir, f'{music.id}.png')
    if os.path.exists(cover_path):
        info.append(Image(cover_path))
    if details:
        info.extend(details)
    return info


async def get_record(msg: Bot.MessageSession, payload: dict, use_cache: bool = True) -> Optional[str]:
    cache_path = os.path.join(cache_dir, f'{msg.target.sender_id.replace('|', '_')}_maimai_record.json')
    url = f"https://www.diving-fish.com/api/chunithmprober/query/player"
    if 'username' in payload:
        use_cache = False
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={'Content-Type': 'application/json', 'accept': '*/*'},
                              fmt='json')
        if use_cache and data:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        return data
    except Exception as e:
        if str(e).startswith('400'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.user_unbound.qq"))
            else:
                await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        elif str(e).startswith('403'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.forbidden.eula"))
            else:
                await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            Logger.error(traceback.format_exc())
        if use_cache and os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                await msg.send_message(msg.locale.t("maimai.message.use_cache"))
                return data
            except Exception:
                raise e
        else:
            raise e
