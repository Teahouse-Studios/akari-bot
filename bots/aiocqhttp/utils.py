import html
import re
from typing import Any

import orjson

from bots.aiocqhttp.info import sender_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image, Voice, Raw
from core.builtins.temp import Temp
from core.logger import Logger
from .client import aiocqhttp_bot


async def get_onebot_implementation() -> str | None:
    """获取正在使用的OneBot实现。"""
    data = await aiocqhttp_bot.call_action("get_version_info")
    Logger.debug(str(data))
    app_name = data.get("app_name")

    if app_name == "NapCat.Onebot":
        app_name = "napcat"
    elif app_name == "Lagrange.OneBot":
        app_name = "lagrange"

    return app_name.lower()


class CQCodeHandler:
    get_supported = ["at", "face", "forward", "image", "json", "record", "text"]
    pattern = re.compile(r"\[CQ:(\w+),?[^\]]*\]")

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
    def generate_cq(data: dict[str, Any]) -> str | None:
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
    def parse_cq(cq_code: str) -> dict[str, str | dict[str, Any]] | None:
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
                        kwargs[html.unescape(ma.group(1))] = orjson.loads(ma.group(2))
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


async def to_message_chain(message: str | list[dict[str, Any]]) -> MessageChain:
    lst = []
    if isinstance(message, str):
        spl = re.split(
            r"(\[CQ:(?:text|image|record|at).*?])", message
        )
        for s in spl:
            if not s:
                continue
            if re.match(r"\[CQ:[^\]]+\]", s):
                cq_data = CQCodeHandler.parse_cq(s)
                if cq_data:
                    if cq_data["type"] == "text":
                        lst.append(Plain(cq_data["data"].get("text")))
                    elif cq_data["type"] == "image":
                        obi = Temp.data.get("onebot_impl")
                        if obi == "lagrange":
                            img_src = cq_data["data"].get("file")
                        else:
                            img_src = cq_data["data"].get("url")
                        if img_src:
                            lst.append(Image(img_src))
                    elif cq_data["type"] == "record":
                        lst.append(Voice(cq_data["data"].get("file")))
                    elif cq_data["type"] == "at":
                        lst.append(Plain(f"{sender_prefix}|{cq_data["data"].get("qq")}"))
                    else:
                        lst.append(Plain(s))
                else:
                    lst.append(Plain(s))
            else:
                lst.append(Plain(s))
    else:
        for item in message:
            if item["type"] == "text":
                lst.append(Plain(item["data"]["text"]))
            elif item["type"] == "image":
                obi = Temp.data.get("onebot_impl")
                if obi == "lagrange":
                    lst.append(Image(item["data"]["file"]))
                else:
                    lst.append(Image(item["data"]["url"]))
            elif item["type"] == "record":
                lst.append(Voice(item["data"]["file"]))
            elif item["type"] == "at":
                lst.append(Plain(f"{sender_prefix}|{item["data"].get("qq")}"))
            else:
                lst.append(Raw(CQCodeHandler.generate_cq(item)))

    return MessageChain.assign(lst)
