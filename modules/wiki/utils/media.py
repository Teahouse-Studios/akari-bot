import filetype

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Audio, Image, Video
from core.logger import Logger
from core.utils.http import download
from core.utils.image import svg_render
from .utils import check_svg


async def file_preview(url: str, session_info) -> MessageChain:
    result = MessageChain.create()
    if not any((session_info.support_image, session_info.support_audio, session_info.support_video)):
        return result
    try:
        path = await download(url)
    except Exception:
        Logger.exception("Failed to download Wiki file preview: ")
        return result
    detected = filetype.guess(path)
    if detected:
        extension = detected.extension
        if extension in {"png", "gif", "jpg", "jpeg", "webp", "bmp", "ico"} and session_info.support_image:
            result.append(Image(path))
        elif extension in {"oga", "ogg", "flac", "mp3", "wav"} and session_info.support_audio:
            result.append(Audio(path))
        elif extension in {"mp4", "mkv", "avi", "mov", "flv", "webm"} and session_info.support_video:
            result.append(Video(path))
    elif session_info.support_image and check_svg(path):
        rendered = await svg_render(path)
        if rendered:
            result.extend(rendered)
    return result
