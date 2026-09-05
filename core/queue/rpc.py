"""Typed RPC declarations shared by callers and handlers.

An endpoint owns the Python signature, wire name and route. Both sides use the
same codec. ``await method(...)`` waits for execution; ``await method.submit``
only waits for acceptance. Submission never promises delivery or retries.
"""

from __future__ import annotations

import inspect
import math
from collections.abc import Awaitable, Callable, Mapping
from copy import copy
from functools import update_wrapper
from typing import Any, Generic, ParamSpec, TypeVar, TYPE_CHECKING, get_type_hints, overload

from . import codec

if TYPE_CHECKING:
    from .base import JobQueueBase


P = ParamSpec("P")
R = TypeVar("R")
Route = str | Callable[[Mapping[str, Any]], str]
_default_peer: type[JobQueueBase] | None = None


def set_default_peer(peer: type[JobQueueBase]) -> None:
    """Set once in the process bootstrap; importing contracts has no such effect."""
    global _default_peer
    _default_peer = peer


def get_default_peer() -> type[JobQueueBase]:
    from .base import current_peer

    peer = current_peer.get() or _default_peer
    if peer is None:
        raise RuntimeError("RPC peer has not been configured for this process")
    return peer


class RpcMethod(Generic[P, R]):
    def __init__(
        self,
        function: Callable[P, Awaitable[R]],
        *,
        name: str,
        target: Route,
        timeout: float = 120,
        context_method: str | None = None,
    ):
        self.name = name
        self.target = target
        self.timeout = timeout
        self.context_method = context_method
        self.signature = inspect.signature(function)
        self.hints = get_type_hints(function)
        self.result_type = self.hints.get("return", type(None))
        for annotation in self.hints.values():
            codec.validate_type(annotation)
        self.peer: type[JobQueueBase] | None = None
        for parameter in self.signature.parameters.values():
            if parameter.name not in self.hints:
                raise TypeError(f"RPC parameter needs an annotation: {name}.{parameter.name}")
            if parameter.kind is parameter.VAR_POSITIONAL:
                raise TypeError("RPC endpoints use named parameters or **kwargs, not *args")
        update_wrapper(self, function)
        self.__signature__ = self.signature

    def using(self, peer: type[JobQueueBase]) -> RpcMethod[P, R]:
        endpoint = copy(self)
        endpoint.peer = peer
        return endpoint

    def with_timeout(self, seconds: float) -> "RpcMethod[P, R]":
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("RPC timeout must be positive and finite")
        endpoint = copy(self)
        endpoint.timeout = seconds
        return endpoint

    def encode_arguments(self, *args: P.args, **kwargs: P.kwargs) -> dict:
        bound = self.signature.bind(*args, **kwargs)
        bound.apply_defaults()
        return {
            name: (
                {key: codec.encode(item, self.hints[name]) for key, item in value.items()}
                if self.signature.parameters[name].kind is inspect.Parameter.VAR_KEYWORD
                else codec.encode(value, self.hints[name])
            )
            for name, value in bound.arguments.items()
        }

    def decode_arguments(self, payload: dict) -> inspect.BoundArguments:
        if not isinstance(payload, dict) or payload.keys() - self.signature.parameters.keys():
            raise TypeError(f"Invalid arguments for {self.name}")
        values = {}
        for name, value in payload.items():
            if self.signature.parameters[name].kind is inspect.Parameter.VAR_KEYWORD:
                if not isinstance(value, dict):
                    raise TypeError("RPC keyword arguments must be a dictionary")
                ordinary_names = set(self.signature.parameters) - {name}
                if value.keys() & ordinary_names:
                    raise TypeError("RPC keyword arguments duplicate declared parameters")
                values[name] = {key: codec.decode(item, self.hints[name]) for key, item in value.items()}
            else:
                values[name] = codec.decode(value, self.hints[name])
        bound = inspect.BoundArguments(self.signature, values)
        # Rebind to reject missing required parameters and malicious **kwargs
        # duplicating an ordinary parameter. Defaults belong to the declaration.
        rebound = self.signature.bind(*bound.args, **bound.kwargs)
        rebound.apply_defaults()
        return rebound

    def _route(self, *args: P.args, **kwargs: P.kwargs) -> str:
        if isinstance(self.target, str):
            return self.target
        bound = self.signature.bind(*args, **kwargs)
        bound.apply_defaults()
        return self.target(bound.arguments)

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        payload = self.encode_arguments(*args, **kwargs)
        peer = self.peer or get_default_peer()
        value = await peer.call(self._route(*args, **kwargs), self.name, payload, timeout=self.timeout)
        return codec.decode(value, self.result_type)

    async def submit(self, *args: P.args, **kwargs: P.kwargs) -> str:
        payload = self.encode_arguments(*args, **kwargs)
        peer = self.peer or get_default_peer()
        return await peer.submit(self._route(*args, **kwargs), self.name, payload, timeout=self.timeout)

    async def dispatch(self, handler: Callable[P, Awaitable[R]], payload: dict) -> Any:
        bound = self.decode_arguments(payload)
        result = handler(*bound.args, **bound.kwargs)
        if inspect.isawaitable(result):
            result = await result
        return codec.encode(result, self.result_type)

    def bind(self, peer: type[JobQueueBase]) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
        def decorator(handler: Callable[P, Awaitable[R]]):
            def shape(signature):
                return [(p.name, p.kind, p.default) for p in signature.parameters.values()]

            if shape(inspect.signature(handler)) != shape(self.signature):
                raise TypeError(f"Handler signature differs from RPC contract: {self.name}")

            async def dispatch(payload):
                return await self.dispatch(handler, payload)

            peer.register(self.name, dispatch)
            return handler

        return decorator

    def bind_context(self, peer, resolver) -> None:
        if self.context_method is None:
            raise ValueError(f"Not a context method: {self.name}")

        async def dispatch(payload):
            bound = self.decode_arguments(payload)
            context = await resolver(bound.arguments["session_info"])
            handler = getattr(context, self.context_method)
            result = handler(*bound.args, **bound.kwargs)
            if inspect.isawaitable(result):
                result = await result
            return codec.encode(result, self.result_type)

        peer.register(self.name, dispatch)


def remote(
    name: str, *, target: Route = "Server", timeout: float = 120
) -> Callable[[Callable[P, Awaitable[R]]], RpcMethod[P, R]]:
    def decorator(function: Callable[P, Awaitable[R]]) -> RpcMethod[P, R]:
        return RpcMethod(function, name=name, target=target, timeout=timeout)

    return decorator


@overload
def context_method(function: Callable[P, Awaitable[R]]) -> RpcMethod[P, R]: ...


@overload
def context_method(function: Callable[P, R]) -> RpcMethod[P, R]: ...


def context_method(function: Callable) -> RpcMethod:
    return RpcMethod(
        function,
        name=f"platform.{function.__name__}",
        target=lambda args: args["session_info"].client_name,
        context_method=function.__name__,
        timeout=7200 if function.__name__ in ("send_message", "send_private_msg") else 120,
    )
