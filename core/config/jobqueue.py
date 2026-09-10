"""JobQueue 配置模板。"""

from uuid import uuid4

from core.config import CFGManager
from core.config.decorator import on_config


@on_config(
    "jobqueue",
    standalone_comments={
        "jobqueue_backend": (
            "config.notes.jobqueue.backend.intro",
            "config.notes.jobqueue.backend.database",
            "config.notes.jobqueue.backend.websocket",
            "config.notes.jobqueue.backend.consistency",
        )
    },
)
class JobQueueConfig:
    jobqueue_backend: str = "websocket"
    jobqueue_node_id: str = ""
    jobqueue_websocket_mode: str = "embedded"
    jobqueue_websocket_url: str = "ws://127.0.0.1:8765/jobqueue"
    jobqueue_websocket_queue_size: int = 1000
    jobqueue_websocket_max_message_bytes: int = 1048576
    jobqueue_websocket_command_timeout: float = 10


@on_config("jobqueue", secret=True)
class JobQueueSecretConfig:
    jobqueue_websocket_token: str = ""


def _is_empty_config_value(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def bootstrap_jobqueue_config() -> tuple[str, ...]:
    """在子进程启动前生成并持久化缺失的 JobQueue 共享配置。

    正常启动只应在 ``pre_init`` 的单写进程中调用本函数。返回值只包含生成的字段名，
    不包含实际密钥，便于调用方记录安全的启动日志。
    """
    generated = []
    if _is_empty_config_value(JobQueueConfig.jobqueue_node_id):
        CFGManager.edit_write("jobqueue_node_id", str(uuid4()), str, table_name="jobqueue")
        generated.append("jobqueue_node_id")

    if _is_empty_config_value(JobQueueSecretConfig.jobqueue_websocket_token):
        # 延迟导入以避免配置模板初始化期间经 core.config.base 形成循环导入。
        from core.utils.random import SecureRandom

        CFGManager.edit_write(
            "jobqueue_websocket_token",
            SecureRandom.token_urlsafe(32),
            str,
            secret=True,
            table_name="jobqueue",
        )
        generated.append("jobqueue_websocket_token")

    return tuple(generated)
