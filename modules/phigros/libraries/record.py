from pathlib import Path

import orjson

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.constants.path import PrivateAssets
from core.logger import Logger

from .PhiCloudActionAsync.ActionLib import countRks, decryptSave, unzipFile
from .assets import load_song_info, to_difficulty_table
from .client import phigros_cloud


def cache_files(union_id: str) -> tuple[Path, Path]:
    """取指定用户的存档缓存路径与元数据路径。

    存放于 PrivateAssets 而非 cache 目录：后者在每次启动时会被整体删除，
    置于其下的回退副本仅在单次运行内有效。

    :param union_id: 用户联合 ID。
    """
    directory = PrivateAssets.path / "phigros" / "saves"
    directory.mkdir(parents=True, exist_ok=True)
    safe = union_id.replace("|", "_")
    return directory / f"{safe}.zip", directory / f"{safe}.json"


def parse_part(save_data: bytes, part: str) -> dict:
    """只解析存档中的指定文件。

    整包解析会让任一文件的结构版本更新波及全部命令，故按需解析。

    :param save_data: 存档压缩包数据。
    :param part: 存档内的文件名，如 gameRecord、gameProgress、settings、gameKey、user。
    """
    return decryptSave(unzipFile(save_data, part))[part]


def get_records(save_data: bytes, song_info: dict | None = None) -> dict:
    """解析成绩并附上定数与等效 rks。

    :param save_data: 存档压缩包数据。
    :param song_info: 曲目信息结构，留空则从磁盘读取。
    """
    if song_info is None:
        song_info = load_song_info()
    return countRks(parse_part(save_data, "gameRecord"), to_difficulty_table(song_info))


async def get_save(msg: Bot.MessageSession, bind_info) -> tuple[bytes, dict]:
    """取存档原始数据与 summary，云端不可用时回落到缓存。

    :param msg: 消息会话，用于在使用缓存时告知用户。
    :param bind_info: 绑定信息记录。
    :return: 存档压缩包数据与 summary。
    """
    zip_file, meta_file = cache_files(bind_info.union_id)
    try:
        async with phigros_cloud(bind_info.session_token, bind_info.is_international) as cloud:
            summary = await cloud.getSummary()
            if zip_file.exists() and meta_file.exists():
                meta = orjson.loads(meta_file.read_bytes())
                if meta.get("checksum") == summary["checksum"]:
                    Logger.debug("Phigros save checksum unchanged, reusing local copy.")
                    return zip_file.read_bytes(), summary
            save_data = await cloud.getSave(summary["url"], summary["checksum"])

        zip_file.write_bytes(save_data)
        meta_file.write_bytes(orjson.dumps({"checksum": summary["checksum"], "summary": summary}))
        return save_data, summary

    except Exception:
        Logger.exception()
        if zip_file.exists() and meta_file.exists():
            try:
                meta = orjson.loads(meta_file.read_bytes())
                await msg.send_message(I18NContext("phigros.message.use_cache"))
                return zip_file.read_bytes(), meta["summary"]
            except Exception:
                Logger.exception()
        raise
