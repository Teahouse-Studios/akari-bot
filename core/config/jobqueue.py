"""JobQueue 配置模板。"""

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
    jobqueue_node_id: str
    jobqueue_websocket_url: str = "ws://127.0.0.1:8765/jobqueue"
    jobqueue_websocket_embedded_hub: bool = True
    jobqueue_websocket_bind_host: str = "127.0.0.1"
    jobqueue_websocket_bind_port: int = 8765
    jobqueue_websocket_queue_size: int = 1000
    jobqueue_websocket_max_message_bytes: int = 1048576
    jobqueue_websocket_command_timeout: float = 10


@on_config("jobqueue", secret=True)
class JobQueueSecretConfig:
    jobqueue_websocket_token: str = ""
