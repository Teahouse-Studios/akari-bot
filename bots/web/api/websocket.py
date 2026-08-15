import asyncio
import os
import re
from collections import defaultdict
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from bots.web.client import app
from core.constants.path import logs_path
from core.logger import Logger

INIT_READ_BYTES = 200 * 1024
INITIAL_MAX_LINES = 100

LOG_HEAD_PATTERN = re.compile(
    r"^\[.+\]\[[a-zA-Z0-9\._]+:[a-zA-Z0-9\._]+:\d+\]\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\[[A-Z]+\]:"
)
LOG_TIME_PATTERN = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


def _log_line_valid(line: str) -> bool:
    return bool(re.match(LOG_HEAD_PATTERN, line))


def _extract_timestamp(line: str):
    match = LOG_TIME_PATTERN.search(line)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    return None


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    current_date = datetime.today().strftime("%Y-%m-%d")

    last_file_pos = defaultdict(int)  # 日志文件当前位置
    last_file_size = defaultdict(int)  # 日志文件大小
    today_logs = list((logs_path).glob(f"*_{current_date}.log"))  # 缓存日志文件列表

    initial_connect = True  # 标记是否为建立连接后的第一次读取

    try:
        while True:
            new_date = datetime.today().strftime("%Y-%m-%d")
            if new_date != current_date:
                last_file_pos.clear()
                last_file_size.clear()
                current_date = new_date
                today_logs = list((logs_path).glob(f"*_{current_date}.log"))
                initial_connect = True

            new_loglines = []
            for log_file in today_logs:
                try:
                    current_size = os.path.getsize(log_file)
                    if log_file in last_file_size and current_size == last_file_size[log_file]:
                        continue

                    last_file_size[log_file] = current_size

                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        if log_file not in last_file_pos:
                            if initial_connect and current_size > INIT_READ_BYTES:
                                f.seek(current_size - INIT_READ_BYTES)
                                f.readline()  # 舍弃第一行（大概率是不完整的半行日志）
                            else:
                                f.seek(0)
                        else:
                            f.seek(last_file_pos[log_file])

                        new_data = f.read()
                        last_file_pos[log_file] = f.tell()

                    if not new_data:
                        continue

                    new_loglines_raw = [line.rstrip() for line in new_data.splitlines() if line.strip()]

                except Exception:
                    Logger.exception()
                    continue

                current_entry = None
                for line in new_loglines_raw:
                    if _log_line_valid(line):
                        if current_entry:
                            new_loglines.append(current_entry)
                        current_entry = line
                    else:
                        if isinstance(current_entry, list):
                            current_entry.append(line)
                        elif isinstance(current_entry, str):
                            current_entry = [current_entry, line]
                if current_entry:
                    new_loglines.append(current_entry)

            if new_loglines:
                if len(today_logs) > 1:
                    new_loglines.sort(
                        key=lambda item: (
                            (_extract_timestamp(item[0]) if isinstance(item, list) else _extract_timestamp(item))
                            or datetime.min
                        )
                    )

                if initial_connect and len(new_loglines) > INITIAL_MAX_LINES:
                    new_loglines = new_loglines[-INITIAL_MAX_LINES:]

                payload = "\n".join("\n".join(item) if isinstance(item, list) else item for item in new_loglines)
                await websocket.send_text(payload)

            initial_connect = False
            await asyncio.sleep(0.2 if new_loglines else 1.0)

    except WebSocketDisconnect:
        pass
    except Exception:
        Logger.exception()
        await websocket.close()
