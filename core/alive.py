from datetime import datetime


class Alive:
    values = {}

    @classmethod
    def refresh_alive(cls, client_name: str, target_prefix_list: list = None, sender_prefix_list: list = None):
        cls.values[client_name] = {}
        cls.values[client_name]["ts"] = datetime.now()
        if target_prefix_list:
            cls.values[client_name]["target_prefix_list"] = target_prefix_list
        if sender_prefix_list:
            cls.values[client_name]["sender_prefix_list"] = sender_prefix_list

    @classmethod
    def get_alive(cls):
        value = {}
        for v in cls.values:
            if "ts" in cls.values[v]:
                if (datetime.now() - cls.values[v]["ts"]).total_seconds() < 120:
                    value.update({v: cls.values[v]})

        return value

    @classmethod
    def determine_target_from(cls, target_id: str):
        """
        确定会话 ID 前缀。

        :param target_id: 会话 ID
        :return: 前缀
        """
        for _, data in cls.get_alive().items():
            for prefix in sorted(data.get("target_prefix_list", []), key=len, reverse=True):
                if target_id.startswith(prefix + "|") or target_id == prefix:
                    return prefix
        return None

    @classmethod
    def determine_sender_from(cls, sender_id: str):
        """
        确定用户 ID 前缀。

        :param sender_id: 用户 ID
        :return: 前缀
        """
        for _, data in cls.get_alive().items():
            for prefix in sorted(data.get("sender_prefix_list", []), key=len, reverse=True):
                if sender_id.startswith(prefix + "|") or sender_id == prefix:
                    return prefix
        return None

    @classmethod
    def determine_client(cls, id: str):
        """
        确定客户端名称。

        :param id: 会话 ID 或用户 ID
        :return: 客户端名称
        """
        for client_name, data in cls.get_alive().items():
            for prefix in sorted(
                    data.get(
                        "target_prefix_list",
                        []) +
                    data.get(
                        "sender_prefix_list",
                        []),
                    key=len,
                    reverse=True):
                if id.startswith(prefix + "|") or id == prefix:
                    return client_name
        return None
