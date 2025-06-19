from typing import Iterable, Optional, Set, Union


class Secret:
    data: Set[str] = set()
    ip_address: Optional[str] = None
    ip_country: Optional[str] = None

    @classmethod
    def add(cls, secret: str):
        if secret:
            cls.data.add(secret.upper())

    @classmethod
    def check(cls, text: str) -> Union[str, bool]:
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
    :param client_name: 客户端名称。
    :param dirty_word_check: 是否启用文本过滤。
    :param web_render_status: WebRender 状态。
    :param use_url_manager: 是否启用 URLManager。
    :param use_url_md_format: 是否启用 URL MarkDown 格式。
    """

    version = None
    subprocess = False
    binary_mode = False
    command_parsed = 0
    client_name = ""
    dirty_word_check = False
    web_render_status = False
    use_url_manager = False
    use_url_md_format = False
