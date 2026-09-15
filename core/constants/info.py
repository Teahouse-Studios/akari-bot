from typing import Iterable


class Secret:
    data: set[str] = set()
    ip_address: str | None = None
    ip_country: str | None = None

    @classmethod
    def add(cls, secret: str):
        if secret:
            cls.data.add(secret.upper())

    @classmethod
    def check(cls, text: str) -> str | bool:
        for secret in cls.data:
            if secret in text.upper():
                return secret
        return False

    @classmethod
    def remove(cls, secret: str):
        if secret and cls.check(secret):
            cls.data.discard(secret.upper())

    @classmethod
    def update(cls, secret: Iterable):
        if secret:
            cls.data.union({s.upper() for s in secret})


class Info:
    """
    机器人信息。

    :param version: 机器人版本。
    :param subprocess: 是否为子进程。
    :param binary_mode: 是否为二进制模式。
    :param command_parsed: 已处理命令数量。
    :param message_parsed: 已处理消息数量。
    :param client_name: 客户端名称。
    :param peer_id: 当前 JobQueue 进程实例 ID。
    :param peer_role: 当前 JobQueue 进程角色。
    :param daemon_pid: 守护进程 PID，由守护进程显式传入，独立运行时为 None。
    :param hub_pid: 内置 JobQueue Hub 子进程 PID，未启用内置 Hub 时为 None。
    :param dirty_word_check: 是否启用文本过滤。
    :param web_render_status: WebRender 状态。
    :param use_url_manager: 是否启用 URLManager。
    :param use_url_md_format: 是否启用 URL MarkDown 格式。
    """

    version = None
    subprocess = False
    binary_mode = False
    command_parsed = 0
    message_parsed = 0
    client_name = ""
    # JobQueue 运行实例 ID 每次进程启动都不同；client_name 仍表示可竞争消费的服务组。
    peer_id = ""
    peer_role = ""
    # 守护进程与内置 Hub 非 JobQueue Peer，其 PID 须由守护进程在 spawn 时显式传入。
    daemon_pid: int | None = None
    hub_pid: int | None = None
    dirty_word_check = False
    web_render_status = False
    use_url_manager = False
    use_url_md_format = False
    http_mock_enabled = False
    # 启用后，mock 未命中的请求直接失败，而不是回落到真实网络。
    # 回落会带上重试与超时（默认 3 次 × 20 秒），足以让单个未录制的 URL 拖慢测试逾一分钟。
    http_mock_strict = False
