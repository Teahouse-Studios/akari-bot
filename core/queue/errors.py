"""Stable RPC failures shared by both sides of the process boundary."""


class RpcError(Exception):
    code = "rpc_error"

    def __init__(self, message: str, *, method: str = "", target: str = "", task_id: str = "", remote_type: str = ""):
        super().__init__(message)
        self.method = method
        self.target = target
        self.task_id = task_id
        self.remote_type = remote_type


class RpcTimeoutError(RpcError, TimeoutError):
    """The deadline expired; a remote side effect may already have happened."""

    code = "timeout"


class RpcRemoteError(RpcError):
    code = "remote_error"


class RpcMethodNotFoundError(RpcRemoteError):
    code = "method_not_found"


class RpcUnavailableError(RpcError):
    code = "unavailable"


class RpcCancelledError(RpcRemoteError):
    """The receiving process stopped an in-flight handler without retrying it."""

    code = "cancelled"


class RpcProtocolError(RpcError):
    code = "protocol_error"


ERROR_TYPES = {
    error.code: error
    for error in (
        RpcTimeoutError,
        RpcRemoteError,
        RpcMethodNotFoundError,
        RpcUnavailableError,
        RpcCancelledError,
        RpcProtocolError,
    )
}
