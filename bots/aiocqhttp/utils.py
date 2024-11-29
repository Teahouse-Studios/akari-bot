import html
import re
from typing import Any, Dict, Optional, Union

import orjson as json

from core.config import Config


def qq_frame_type() -> str:
    '''获取正在使用的QQ机器人框架'''
    frame_type = Config('qq_frame_type', 'mirai', table_name='bot_aiocqhttp').lower()
    ntqq_lst = ['ntqq', 'llonebot', 'napcat', 'napcatqq', ]
    shamrock_lst = ['shamrock', 'openshamrock', ]
    lagrange_lst = ['lagrange', ]
    mirai_lst = ['mirai', 'gocq', 'gocqhttp', 'go-cqhttp', ]

    if frame_type in ntqq_lst:
        return 'ntqq'
    elif frame_type in lagrange_lst:
        return 'lagrange'
    elif frame_type in shamrock_lst:
        return 'shamrock'
    elif frame_type in mirai_lst:
        return 'mirai'
    else:
        return ''


class CQCodeHandler:
    get_supported = ['at', 'face', 'forward', 'image', 'json', 'record', 'text']
    pattern = re.compile(r'\[CQ:(\w+),[^\]]*\]')

    @staticmethod
    def filter_cq(s: str) -> str:
        """
        过滤CQ码，返回支持的CQ码。

        :param s: 正则匹配对象，包含CQ码的字符串消息。
        :return: 如果CQ类型在支持列表中，返回原CQ码；否则返回空字符串。
        """
        return CQCodeHandler.pattern.sub(lambda m: m.group(0) if m.group(1) in CQCodeHandler.get_supported else '', s)

    @staticmethod
    def generate_cq(data: Dict[str, Any]) -> Optional[str]:
        """
        生成CQ码字符串。

        :param data: 包含CQ类型和参数的字典，必须包含'type'和'data'字段。
        :return: 生成的CQ码字符串；如果输入数据无效，返回None。
        """
        if 'type' in data and 'data' in data:
            cq_type = data['type']
            params = data['data']
            param_str = [f"{key}={CQCodeHandler.escape_special_char(str(value))}"
                         for key, value in params.items()]
            cq_code = f"[CQ:{cq_type}," + ",".join(param_str) + "]"
            return cq_code
        else:
            return None

    @staticmethod
    def parse_cq(cq_code: str) -> Optional[Dict[str, Union[str, Dict[str, Any]]]]:
        """
        解析CQ码字符串，返回包含类型和参数的字典。

        :param cq_code: CQ码字符串。
        :return: 包含CQ类型和参数的字典；如果CQ码格式不正确，返回None。
        """
        match = re.match(r'\[CQ:(\w+),(.+?)\]', cq_code)
        if not match:
            return None

        cq_type = match.group(1)
        parameters = match.group(2)

        param_dict = {}
        if cq_type == "json":
            for param in parameters.split(','):
                key, value = param.split('=')
                value = html.unescape(value)
                param_dict[key] = json.loads(value)
        else:
            for param in parameters.split(','):
                key, value = param.split('=')
                param_dict[key] = html.unescape(value)

        data = {
            "type": cq_type,
            "data": param_dict
        }

        return data

    @staticmethod
    def escape_special_char(s: str, escape_comma: bool = True) -> str:
        """
        转义CQ码中的特殊字符。

        :param s: 要转义的字符串。
        :param escape_comma`` 是否转义逗号（``,``）。
        :return: 转义后的字符串。
        """
        s = s.replace('&', '&amp;').replace('[', '&#91;').replace(']', '&#93;')
        s = s.replace('/', '\\/').replace('\\\\/', '\\/')
        if escape_comma:
            s = s.replace(',', '&#44;')
        return s
