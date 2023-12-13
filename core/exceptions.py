class AbuseWarning(Exception):
    pass


class ConfigFileNotFound(Exception):
    pass


class InvalidHelpDocTypeError(Exception):
    pass


class InvalidCommandFormatError(Exception):
    pass


class FinishedException(BaseException):
    pass


class WaitCancelException(BaseException):
    pass


class SendMessageFailed(BaseException):
    pass


class InvalidTemplatePattern(Exception):
    pass


class NoReportException(Exception):
    pass

class TestException(Exception):
    pass
