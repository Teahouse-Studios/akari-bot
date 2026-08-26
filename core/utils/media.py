"""发送前的音视频压缩工具。"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import AudioElement, VideoElement
from core.config.base import CoreConfig
from core.logger import Logger
from core.utils.cache import random_cache_path


async def compress_media_chain(chain: MessageChain) -> MessageChain:
    """压缩超出阈值的音视频；配置不完整或缺失 ffmpeg 时原样返回。压缩失败时跳过对应元素，体积变大则使用原文件。"""
    ffmpeg_path = CoreConfig.ffmpeg_path
    threshold = CoreConfig.media_compression_threshold

    if not ffmpeg_path or threshold <= 0:
        return chain

    # 提前校验并解析 ffmpeg 可执行文件路径
    resolved_ffmpeg = shutil.which(ffmpeg_path)
    if resolved_ffmpeg is None and not Path(ffmpeg_path).is_file():
        Logger.error(f"ffmpeg not found: {ffmpeg_path}")
        return chain
    resolved_ffmpeg = resolved_ffmpeg or ffmpeg_path

    threshold_bytes = threshold * 1024 * 1024

    # 建立新消息链，用于存放入选的元素
    compressed = deepcopy(chain)
    valid_elements = []

    for element in compressed.values:
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

        output = Path(f"{random_cache_path()}{'.mp3' if isinstance(element, AudioElement) else '.mp4'}")
        command = [resolved_ffmpeg, "-y", "-i", str(source)]

        if isinstance(element, AudioElement):
            command += ["-vn", "-c:a", "libmp3lame", "-b:a", "128k"]
        else:
            command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "128k"]

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
                continue

            compressed_size = output.stat().st_size

            # 若压缩后体积没有变小，改用原来的多媒体路径并清理临时文件
            if compressed_size >= source_size:
                Logger.warning(
                    f"Compressed size ({compressed_size} bytes) of \"{source}\" is not smaller than original ({source_size} bytes)."
                )
                output.unlink(missing_ok=True)
                valid_elements.append(element)
                continue

            # 压缩成功且体积减小
            element.path = str(output)
            valid_elements.append(element)

        except (OSError, subprocess.SubprocessError):
            Logger.exception(f"Failed to run ffmpeg for {source}: ")
            output.unlink(missing_ok=True)
            continue

    compressed.values = valid_elements
    return compressed


__all__ = ["compress_media_chain"]
