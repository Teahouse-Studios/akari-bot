import html
import re
from typing import Any, Dict, Optional, Union, List

import orjson as json

from bots.aiocqhttp.client import bot
from core.logger import Logger


async def get_onebot_implementation() -> Optional[str]:
    """获取正在使用的OneBot实现。"""
    data = await bot.call_action("get_version_info")
    Logger.debug(str(data))
    app_name = data.get("app_name")

    if app_name == "NapCat.Onebot":
        app_name = "napcat"
    elif app_name == "Lagrange.OneBot":
        app_name = "lagrange"

    return app_name.lower()


class CQCodeHandler:
    get_supported = ["at", "face", "forward", "image", "json", "record", "text"]
    pattern = re.compile(r"\[CQ:(\w+),[^\]]*\]")

    @staticmethod
    def filter_cq(s: str) -> str:
        """
        过滤CQ码，返回支持的CQ码。

        :param s: 正则匹配对象，包含CQ码的字符串消息。
        :return: 如果CQ类型在支持列表中，返回原CQ码；否则返回空字符串。
        """
        return CQCodeHandler.pattern.sub(
            lambda m: m.group(0) if m.group(1) in CQCodeHandler.get_supported else "", s
        )

    @staticmethod
    def generate_cq(data: Dict[str, Any]) -> Optional[str]:
        """
        生成CQ码字符串。

        :param data: 包含CQ类型和参数的字典，必须包含`type`和`data`字段。
        :return: 生成的CQ码字符串；如果输入数据无效，返回None。
        """
        if "type" in data and "data" in data:
            cq_type = data["type"]
            params = data["data"]

            if not params:
                return f"[CQ:{cq_type}]"
            param_str = [
                f"{key}={CQCodeHandler.escape_special_char(str(value))}"
                for key, value in params.items()
            ]
            return f"[CQ:{cq_type},{", ".join(param_str)}]"
        return None

    @staticmethod
    def parse_cq(cq_code: str) -> Optional[Dict[str, Union[str, Dict[str, Any]]]]:
        """
        解析CQ码字符串，返回包含类型和参数的字典。

        :param cq_code: CQ码字符串。
        :return: 包含CQ类型和参数的字典；如果CQ码格式不正确，返回None。
        """
        kwargs = {}
        match = re.match(r"\[CQ:([^\s,\]]+)(?:,([^\]]+))?\]", cq_code)
        if not match:
            return None
        cq_type = match.group(1)
        if match.group(2):
            params = match.group(2).split(",")
            params = [x for x in params if x]
            for a in params:
                ma = re.match(r"(.*?)=(.*)", a)
                if ma:
                    if cq_type == "json":
                        kwargs[html.unescape(ma.group(1))] = json.loads(ma.group(2))
                    else:
                        kwargs[html.unescape(ma.group(1))] = html.unescape(ma.group(2))
        data = {"type": cq_type, "data": kwargs}

        return data

    @staticmethod
    def escape_special_char(s: str, escape_comma: bool = True) -> str:
        """
        转义CQ码中的特殊字符。

        :param s: 要转义的字符串。
        :param escape_comma: 是否转义逗号（`,`）。
        :return: 转义后的字符串。
        """
        s = s.replace("&", "&amp;").replace("[", "&#91;").replace("]", "&#93;")
        s = s.replace("/", "\\/").replace("\\\\/", "\\/")
        if escape_comma:
            s = s.replace(",", "&#44;")
        return s
