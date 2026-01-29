class SendMessageFailed(BaseException):
    pass


class SessionFinished(BaseException):
    pass


class WaitCancelException(BaseException):
    pass


class AbuseWarning(Exception):
    pass


class ConfigFileNotFound(Exception):
    pass


class ConfigOperationError(Exception):
    pass


class ConfigValueError(Exception):
    pass


class ExternalException(Exception):
    pass


class InvalidCommandFormatError(Exception):
    pass


class InvalidHelpDocTypeError(Exception):
    pass


class InvalidTemplatePattern(Exception):
    pass


class NoReportException(Exception):
    pass


class QueueAlreadyRunning(Exception):
    pass


class TestException(Exception):
    pass
