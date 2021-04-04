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
        if value is not None:
            return value
        for key, value in self.data.items():
            if isinstance(key, tuple) and key[0] <= error <= key[1]:
                return value

        return None

    # If your modules require specific extra info for error ranges, add it here
    def get_summary(self, summary: int):
        value = self.summaries.get(summary, None)
        if value is not None:
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
    def __init__(self, name: str, *, message_str: str = '', supplementary_value: int = None):
        self.field_name = name

        try:
            self.message = message_str
        except KeyboardInterrupt:
            raise
        except:
            self.message = ''

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
    def __init__(self, error: str, console_name: str, color: int, extra_description: str = None, secondary_error: str = None):
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
REPORT_DETAILS = 'You should report relevant details to \
[the Kurisu repository](https://github.com/nh-server/Kurisu/issues).'

UNKNOWN_MODULE = ResultInfo(f'Invalid or unknown module. Are you sure you \
typed the error code in correctly? {REPORT_DETAILS}')

NO_RESULTS_FOUND = ResultInfo(f'I know about this module, but I don\'t have any \
information on error codes for it. {REPORT_DETAILS}')

BANNED_FIELD = ConsoleErrorField('Console, account and game bans', message_str='Nintendo Homebrew does not provide support \
for unbanning. Please do not ask for further assistance with this.')

WARNING_COLOR = 0xFFFF00

UNKNOWN_CATEGORY_DESCRIPTION = ConsoleErrorField('Description', message_str=f'Your support description appears to be unknown. {REPORT_DETAILS}')
