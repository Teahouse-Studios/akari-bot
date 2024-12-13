class Secret:
    list = []
    ip_address = None
    ip_country = None

    @classmethod
    def add(cls, secret):
        cls.list.append(secret)


class Info:
    version = None
    subprocess = False
    binary_mode = False
    command_parsed = 0
    client_name = ''
    dirty_word_check = False
    web_render_status = False
    web_render_local_status = False
    use_url_manager = False
    use_url_md_format = False
