import os
import traceback
from typing import Optional

import ujson as json

from config import Config
from core.builtins import Bot, Plain
from core.logger import Logger
from core.utils.http import post_url
from .chunithm_music import Music

cache_dir = os.path.abspath(Config('cache_path', './cache/'))


async def get_info(music: Music, *details):
    info = [Plain(f"{music.id}\u200B. {music.title}")]
    # 此处未来会添加图片
    if details:
        info.extend(details)
    return info


async def get_record(msg: Bot.MessageSession, payload: dict) -> Optional[str]:
    cache_path = os.path.join(cache_dir, f'{msg.target.sender_id.replace('|', '_')}_maimai_record.json')
    url = f"https://www.diving-fish.com/api/chunithmprober/query/player"
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={'Content-Type': 'application/json', 'accept': '*/*'},
                              fmt='json')
        if data:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        return data
    except ValueError as e:
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
    except Exception:
        Logger.error(traceback.format_exc())
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                await msg.send_message(msg.locale.t("maimai.message.use_cache"))
                return data
            except Exception:
                return None
