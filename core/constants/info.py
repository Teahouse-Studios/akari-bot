class Secret:
    list = []
    ip_address = None
    ip_country = None

    @classmethod
    def add(cls, secret):
        cls.list.append(secret)


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
    :param web_render_local_status: 本地 WebRender 状态。
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
    web_render_local_status = False
    use_url_manager = False
    use_url_md_format = False
