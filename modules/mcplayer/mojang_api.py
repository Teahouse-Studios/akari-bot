import os

import orjson as json
from PIL import Image as PILImage

from core.constants.path import cache_path
from core.logger import Logger
from core.utils.http import get_url, download


async def uuid_to_name(uuid):
    res = json.loads(
        await get_url(f"https://api.mojang.com/user/profiles/{uuid}/names", 200)
    )
    return res[0]["name"]


async def name_to_uuid(name):
    res = json.loads(
        await get_url(f"https://api.mojang.com/users/profiles/minecraft/{name}", 200)
    )
    return res["id"]


async def uuid_to_skin_and_cape(uuid):
    try:
        render = await download(
            "https://crafatar.com/renders/body/" + uuid + "?overlay"
        )
        skin = await download("https://crafatar.com/skins/" + uuid)
        is_cape = True
        try:
            await get_url(
                "https://crafatar.com/capes/" + uuid, 200, logging_err_resp=False
            )
        except ValueError:
            is_cape = False
        path = None
        if is_cape:
            cape = PILImage.open(await download("https://crafatar.com/capes/" + uuid))
            cape.crop((0, 0, 10, 16))
            path = os.path.join(cache_path, f"{uuid}_fixed.png")
            cape.save(path)
        return {"render": render, "skin": skin, "cape": path}
    except Exception:
        Logger.warning("Unable to render player module, skip.")
        return None


__all__ = ["uuid_to_name", "name_to_uuid", "uuid_to_skin_and_cape"]
