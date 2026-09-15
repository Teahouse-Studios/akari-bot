from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core.config.base import CoreSecretConfig
from core.constants import database_path

SQLITE_CONNECTION_DEFAULTS = {
    # Tortoise 按参数顺序执行 PRAGMA。先延长锁等待时间，再尝试切换 WAL，
    # 避免多个进程并发启动时 journal_mode 尚未受到 30 秒等待策略保护。
    "busy_timeout": "30000",
    "journal_mode": "WAL",
}

db_link = CoreSecretConfig.db_path
db_parts = db_link.split("://")
db_type = db_parts[0].split("+")[0] if db_parts else "sqlite"
db_path = database_path

if db_type == "sqlite":
    db_path = Path(db_link.replace("sqlite://", "")).parent
db_path.mkdir(parents=True, exist_ok=True)


def prepare_db_link(link: str) -> str:
    parts = link.split("://", 1)
    link_type = parts[0].split("+")[0] if parts else "sqlite"
    normalized_link = f"{link_type}://{parts[1]}" if len(parts) > 1 else link
    if link_type != "sqlite":
        return normalized_link

    parsed = urlsplit(normalized_link)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    existing_fields = {key.lower() for key, _ in query}
    query.extend((key, value) for key, value in SQLITE_CONNECTION_DEFAULTS.items() if key not in existing_fields)
    # busy_timeout 必须在可能取得写锁的 PRAGMA（尤其 journal_mode）之前生效；
    # 即使调用方显式提供了参数并采用其它排列，也统一提前执行等待策略。
    query.sort(key=lambda item: item[0].lower() != "busy_timeout")
    return urlunsplit(parsed._replace(query=urlencode(query)))


def get_db_link():
    return prepare_db_link(db_link)
