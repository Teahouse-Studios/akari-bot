from __future__ import annotations

import asyncio
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

from PIL import Image as PILImage

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import AudioElement, ImageElement, VideoElement
from core.config.base import CoreConfig
from core.logger import Logger
from core.utils.cache import random_cache_path

ffmpeg_path = CoreConfig.ffmpeg_path
threshold = CoreConfig.media_compression_threshold


def compress_image(element: ImageElement, threshold_bytes: int) -> ImageElement:
    source = Path(element.path)
    try:
        source_size = source.stat().st_size
        if source_size <= threshold_bytes:
            return element

        with PILImage.open(source) as image:
            has_transparency = image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info
            output_format = "WEBP" if has_transparency else "JPEG"
            output = random_cache_path("webp" if has_transparency else "jpg")
            converted = image.convert("RGBA" if has_transparency else "RGB")
            save_options = (
                {"quality": 85, "method": 6}
                if has_transparency
                else {
                    "quality": 85,
                    "optimize": True,
                    "progressive": True,
                }
            )
            converted.save(output, format=output_format, **save_options)

        if output.stat().st_size >= source_size:
            output.unlink(missing_ok=True)
            return element

        element.path = str(output)
        element.cached_b64 = None
        return element
    except (OSError, PILImage.UnidentifiedImageError):
        Logger.exception(f"Failed to compress image {source}: ")
        if "output" in locals():
            output.unlink(missing_ok=True)
        return element


async def compress_audio_video(element: AudioElement | VideoElement, ffmpeg_path: str) -> AudioElement | VideoElement:
    source = Path(element.path)
    output = Path(f"{random_cache_path()}{'.mp3' if isinstance(element, AudioElement) else '.mp4'}")
    command = [ffmpeg_path, "-y", "-i", str(source)]

    if isinstance(element, AudioElement):
        command += ["-vn", "-c:a", "libmp3lame", "-b:a", "64k", "-ar", "44100"]
    else:
        command += [
            "-c:v",
            "libx264",
            "-preset",
            "faster",
            "-crf",
            "30",
            "-vf",
            "scale='min(1280\\,iw)':-2",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
        ]

    command.append(str(output))
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0 or not output.exists():
            detail = stderr.decode(errors="replace")[-500:]
            Logger.error(f"Failed to compress media {source}: {detail}")
            output.unlink(missing_ok=True)
            return element

        source_size = source.stat().st_size
        compressed_size = output.stat().st_size
        if compressed_size >= source_size:
            Logger.warning(f"Compressed size ({compressed_size} B) is not smaller than original ({source_size} B).")
            output.unlink(missing_ok=True)
            return element

        element.path = str(output)
        if isinstance(element, ImageElement):
            element.cached_b64 = None
        return element
    except (OSError, subprocess.SubprocessError):
        Logger.exception(f"Failed to run ffmpeg for {source}: ")
        output.unlink(missing_ok=True)
        return element


async def compress_media_chain(chain: MessageChain) -> MessageChain:
    if threshold <= 0:
        return chain

    threshold_bytes = int(threshold * 1024 * 1024)
    compressed = deepcopy(chain)
    valid_elements = []
    resolved_ffmpeg = None

    for element in compressed.values:
        if isinstance(element, ImageElement):
            valid_elements.append(compress_image(element, threshold_bytes))
            continue
        if not isinstance(element, (AudioElement, VideoElement)):
            valid_elements.append(element)
            continue

        source = Path(element.path)
        try:
            source_size = source.stat().st_size
        except OSError:
            Logger.exception(f"Unable to inspect media file {source}: ")
            continue

        # 小于等于阈值，无需压缩，直接保留
        if source_size <= threshold_bytes:
            valid_elements.append(element)
            continue

        if resolved_ffmpeg is None:
            resolved_ffmpeg = shutil.which(ffmpeg_path)
            if resolved_ffmpeg is None and not Path(ffmpeg_path).is_file():
                Logger.error(f"FFmpeg not found: {ffmpeg_path}")
                valid_elements.append(element)
                continue
            resolved_ffmpeg = resolved_ffmpeg or ffmpeg_path

        valid_elements.append(await compress_audio_video(element, resolved_ffmpeg))

    compressed.values = valid_elements
    return compressed


__all__ = ["compress_image", "compress_audio_video", "compress_media_chain"]
