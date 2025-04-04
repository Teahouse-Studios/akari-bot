import traceback
from typing import Optional

import orjson as json

from core.builtins import Bot, Image, MessageChain, Plain
from core.constants.path import cache_path
from core.logger import Logger
from core.utils.http import post_url
from .chunithm_mapping import *
from .chunithm_music import Music


async def get_info(music: Music, *details) -> MessageChain:
    info = [Plain(f"{music.id} - {music.title}")]
    cover_path = os.path.join(chu_cover_path, f"{music.id}.png")
    if os.path.exists(cover_path):
        info.append(Image(cover_path))
    if details:
        info.extend(details)
    return info


async def get_record(msg: Bot.MessageSession, payload: dict, use_cache: bool = True) -> Optional[str]:
    maimai_cache_dir = os.path.join(cache_path, "maimai-record")
    os.makedirs(maimai_cache_dir, exist_ok=True)
    cache_dir = os.path.join(maimai_cache_dir, f"{msg.target.sender_id.replace("|", "_")}_chunithm_record.json")
    url = "https://www.diving-fish.com/api/chunithmprober/query/player"
    if "username" in payload:
        use_cache = False
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={"Content-Type": "application/json", "accept": "*/*"},
                              fmt="json")
        if use_cache and data:
            with open(cache_dir, "wb") as f:
                f.write(json.dumps(data))
        return data
    except Exception as e:
        if str(e).startswith("400"):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.user_unbound.qq"))
            else:
                await msg.finish(msg.locale.t("maimai.message.user_not_found"))
        elif str(e).startswith("403"):
            if "qq" in payload:
                await msg.finish(msg.locale.t("maimai.message.forbidden.eula"))
            else:
                await msg.finish(msg.locale.t("maimai.message.forbidden"))
        else:
            Logger.error(traceback.format_exc())
        if use_cache and os.path.exists(cache_dir):
            try:
                with open(cache_dir, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                await msg.send_message(msg.locale.t("maimai.message.use_cache"))
                return data
            except Exception:
                raise e
        else:
            raise e
