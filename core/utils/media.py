"""发送前的音视频压缩工具。"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import AudioElement, VideoElement
from core.config.base import CoreConfig
from core.logger import Logger


async def compress_media_chain(chain: MessageChain) -> MessageChain | None:
    """压缩超出阈值的音视频；配置不完整时原样返回。压缩失败或超过阈值时跳过对应元素。"""
    ffmpeg_path = CoreConfig.ffmpeg_path.strip()
    threshold = CoreConfig.media_compression_threshold
    if not ffmpeg_path or threshold <= 0:
        return chain

    threshold_bytes = threshold * 1024 * 1024
    resolved_ffmpeg = None

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

        # 检查 ffmpeg 可执行文件路径
        if resolved_ffmpeg is None:
            resolved_ffmpeg = shutil.which(ffmpeg_path)
            if resolved_ffmpeg is None and not Path(ffmpeg_path).is_file():
                Logger.warning(f"ffmpeg not found: {ffmpeg_path}")
                continue
            resolved_ffmpeg = resolved_ffmpeg or ffmpeg_path

        output_suffix = ".mp3" if isinstance(element, AudioElement) else ".mp4"
        with tempfile.NamedTemporaryFile(prefix="akari-compressed-", suffix=output_suffix, delete=False) as file:
            output = Path(file.name)

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
                Logger.warning(f"Failed to compress media {source}: {detail}")
                output.unlink(missing_ok=True)
                continue

            compressed_size = output.stat().st_size
            # 校验：压缩后大小是否依然大于阈值，或未能实现缩小
            if compressed_size > threshold_bytes or compressed_size >= source_size:
                Logger.warning(
                    f"Compressed file still exceeds the threshold ({compressed_size} > {threshold_bytes} bytes). Skipped {source}."
                )
                output.unlink(missing_ok=True)
                continue

            # 压缩成功且达标
            element.path = str(output)
            valid_elements.append(element)

        except (OSError, subprocess.SubprocessError):
            Logger.exception(f"Failed to run ffmpeg for {source}: ")
            output.unlink(missing_ok=True)
            continue

    compressed.values = valid_elements
    return compressed


__all__ = ["compress_media_chain"]
