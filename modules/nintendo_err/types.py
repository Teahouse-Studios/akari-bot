from typing import Optional

from core.builtins import Url


class Module:
    """
    Describes a Module. A Module contains a dictionary of ResultCodes,
    and possibly a second dictionary with extra information.
    A module itself is basically who raised the error or returned the result.
    """

    def __init__(self, name, data={}, summaries={}):
        self.name = name
        self.data = data
        self.summaries = summaries

    def get_error(self, error: int):
        value = self.data.get(error, None)
        if value:
            return value
        for key, value in self.data.items():
            if isinstance(key, tuple) and key[0] <= error <= key[1]:
                return value

        return None

    # If your modules require specific extra info for error ranges, add it here
    def get_summary(self, summary: int):
        value = self.summaries.get(summary, None)
        if value:
            return value
        for key, value in self.summaries.items():
            if isinstance(key, tuple) and key[0] <= summary <= key[1]:
                return value

        return None


class ResultInfo:
    """
    Holds information on a result or support code. A ResultInfo has a few fields which are used
    to provide information about the result, error, or support code, including a support
    webpage, if available.
    """

    def __init__(self, description='', support_url='', is_ban=False):
        self.description = description
        self.support_url = support_url
        self.is_ban = is_ban


class ConsoleErrorField:
    def __init__(self, name: str, *, message_str: str = '', supplementary_value: Optional[int] = None):

        self.field_name = name
        self.message = message_str

        if supplementary_value is None:
            return

        try:
            supplementary_value = int(supplementary_value)
        except ValueError:
            return
        self.message = f"{self.message} ({supplementary_value})" if self.message else f"{supplementary_value}"


class ConsoleErrorInfo:
    """
    Holds the console name, the embed fields by an iteration of the parsed error or support code
    """

    def __init__(self, error: str, console_name: str, color: int, extra_description: Optional[str] = None,
                 secondary_error: Optional[str] = None):
        self.error = error
        self.secondary_error = secondary_error
        self.console_name = console_name
        self.color = color
        self.fields = []
        self.secondary_error = secondary_error
        self.extra_description = extra_description

    def __iter__(self):
        return iter(self.fields)

    def get_title(self):
        if self.secondary_error:
            return f"{self.error}/{self.secondary_error} ({self.console_name})"
        else:
            return f"{self.error} ({self.console_name})"

    def add_field(self, field: ConsoleErrorField):
        self.fields.append(field)


# Helper constants
REPORT_DETAILS = '你应该向本模块的原仓库发起Issue来添加有关内容（请说英文）：' + str(
    Url('https://github.com/nh-server/Kurisu/issues'))

UNKNOWN_MODULE = ResultInfo(f'无效/未知的module。请问你正确输入错误代码了吗？{REPORT_DETAILS}')

NO_RESULTS_FOUND = ResultInfo(f'我知道这个module。但是我没有任何有关这个错误的记载。{REPORT_DETAILS}')

BANNED_FIELD = ConsoleErrorField('致主机、账户或游戏被封禁者',
                                 message_str='我们不会提供解封服务，所以也请不要试图在这里获得谁的帮助。')

WARNING_COLOR = 0xFFFF00

UNKNOWN_CATEGORY_DESCRIPTION = ConsoleErrorField('描述', message_str=f'对应你的报错描述未知。{REPORT_DETAILS}')
