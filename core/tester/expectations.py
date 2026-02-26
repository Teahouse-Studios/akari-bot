from __future__ import annotations

import asyncio
import re
from typing import Callable

from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.builtins.types import MessageElement, MultimodalElement


class Expectation:
    """
    所有期望匹配器的基类。
    """

    async def match(self, result: dict) -> bool:
        raise NotImplementedError

    def __and__(self, other: "Expectation") -> "Expectation":
        return All(self, other)

    def __or__(self, other: "Expectation") -> "Expectation":
        return Any(self, other)

    def __invert__(self) -> "Expectation":
        return Not(self)


class All(Expectation):
    """
    满足所有期望匹配器。

    :param expects: 期望匹配器
    """

    def __init__(self, *expects: Expectation):
        self.expects = expects

    async def match(self, result):
        for e in self.expects:  # skipcq
            if not await e.match(result):
                return False
        return True

    def __str__(self):
        return f"({' AND '.join(str(e) for e in self.expects)})"


class Any(Expectation):
    """
    满足任意期望匹配器。

    :param expects: 期望匹配器
    """

    def __init__(self, *expects: Expectation):
        self.expects = expects

    async def match(self, result):
        for e in self.expects:  # skipcq
            if await e.match(result):
                return True
        return False

    def __str__(self):
        return f"({' OR '.join(str(e) for e in self.expects)})"


class Not(Expectation):
    """
    不允许满足某一期望匹配器。

    :param expect: 期望匹配器
    """

    def __init__(self, expect: Expectation):
        self.expect = expect

    async def match(self, result):
        r = await self.expect.match(result)
        return not r

    def __str__(self):
        return f"NOT {self.expect}"


class Empty(Expectation):
    """
    是否无输出。
    """

    async def match(self, result):
        return not bool(result.get("output"))

    def __str__(self):
        return "Empty()"


class Equal(Expectation):
    """
    是否完全匹配消息链。

    :param msg_chain: 期望消息链
    """

    def __init__(
        self, msg_chain: str | MessageChain | list[MessageElement] | tuple[MessageElement, ...] | MessageElement
    ):
        self.expected = msg_chain

    async def match(self, result):
        session_info = await SessionInfo.assign(
            target_id="TEST|Console|0",
            client_name="TEST",
            target_from="TEST",
            sender_id="TEST|0",
            sender_from="TEST",
        )

        expected = MessageChain.assign(self.expected).as_sendable(session_info)
        actual = MessageChain.assign(result.get("output")).as_sendable(session_info)
        return expected == actual

    def __str__(self):
        return f"Equal({MessageChain.assign(self.expected).to_str(text_only=False, connector=' ')!r})"


class Match(Expectation):
    """
    消息文本是否匹配。

    :param msg_chain: 期望消息链
    :param case_sensitive: 是否大小写敏感，默认 False
    """

    def __init__(
        self,
        msg_chain: str | MessageChain | list[MessageElement] | tuple[MessageElement, ...] | MessageElement,
        case_sensitive: bool = False,
    ):
        self.expected = msg_chain
        self.case_sensitive = case_sensitive

    async def match(self, result):
        expected = MessageChain.assign(self.expected).to_str()
        actual = MessageChain.assign(result.get("output")).to_str()
        if not self.case_sensitive:
            expected = expected.lower()
            actual = actual.lower()
        return expected == actual

    def __str__(self):
        return (
            f"Match({MessageChain.assign(self.expected).to_str(connector=' ')!r}, case_sensitive={self.case_sensitive})"
        )


class Contains(Expectation):
    """
    消息文本中是否包含特定字符串。

    :param text: 期望字符串
    :param case_sensitive: 是否大小写敏感，默认 False
    """

    def __init__(self, text: str, case_sensitive: bool = False):
        self.text = text
        self.case_sensitive = case_sensitive

    async def match(self, result):
        text = self.text
        output = MessageChain.assign(result.get("output")).to_str()
        if not self.case_sensitive:
            text = text.lower()
            output = output.lower()
        return text in output

    def __str__(self):
        return f"Contains({self.text!r}, case_sensitive={self.case_sensitive})"


class StartsWith(Expectation):
    """
    消息文本开头是否包含特定字符串。

    :param text: 期望字符串
    :param case_sensitive: 是否大小写敏感，默认 False
    """

    def __init__(self, text: str, case_sensitive: bool = False):
        self.text = text
        self.case_sensitive = case_sensitive

    async def match(self, result):
        text = self.text
        output = MessageChain.assign(result.get("output")).to_str()
        if not self.case_sensitive:
            text = text.lower()
            output = output.lower()
        return output.startswith(text)

    def __str__(self):
        return f"StartsWith({self.text!r}, case_sensitive={self.case_sensitive})"


class EndsWith(Expectation):
    """
    消息文本结尾是否包含特定字符串。

    :param text: 期望字符串
    :param case_sensitive: 是否大小写敏感，默认 False
    """

    def __init__(self, text: str, case_sensitive: bool = False):
        self.text = text
        self.case_sensitive = case_sensitive

    async def match(self, result):
        text = self.text
        output = MessageChain.assign(result.get("output")).to_str()
        if not self.case_sensitive:
            text = text.lower()
            output = output.lower()
        return output.endswith(text)

    def __str__(self):
        return f"EndsWith({self.text!r}, case_sensitive={self.case_sensitive})"


class Regex(Expectation):
    """
    消息文本中是否满足正则表达式。

    :param pattern: 正则表达式
    :param flags: 匹配方式
    """

    def __init__(self, pattern: str | re.Pattern, flags: re.RegexFlag = 0):
        self.pattern = re.compile(pattern, flags) if isinstance(pattern, str) else pattern

    async def match(self, result):
        output = MessageChain.assign(result.get("output")).to_str()
        return bool(self.pattern.search(output))

    def __str__(self):
        return f"Regex({self.pattern.pattern!r})"


class Length(Expectation):
    """
    消息链长度是否符合预期。

    :param eq: 预期消息链精确长度
    :param ge: 预期消息链最小长度
    :param le: 预期消息链最大长度
    """

    def __init__(self, eq: int | None = None, ge: int | None = None, le: int | None = None):
        self.eq = eq
        self.ge = ge
        self.le = le

    async def match(self, result):
        output = result.get("output") or []

        if self.eq is not None and len(output) != self.eq:
            return False
        if self.ge is not None and len(output) < self.ge:
            return False
        if self.le is not None and len(output) > self.le:
            return False
        return True

    def __str__(self):
        parts = []
        if self.eq is not None:
            parts.append(f"eq={self.eq}")
        if self.ge is not None:
            parts.append(f"ge={self.ge}")
        if self.le is not None:
            parts.append(f"le={self.le}")
        return f"Length({', '.join(parts)})"


class Exist(Expectation):
    """
    消息链中是否含有对应消息元素类型。

    :param element: 消息元素类型
    :param func: 自定义函数
    """

    def __init__(self, element: type[MultimodalElement], func: Callable | None = None):
        self.element = element
        self.func = func

    async def match(self, result):
        output = result.get("output") or []

        for e in output:
            if isinstance(e, self.element):
                if self.func:
                    if asyncio.iscoroutinefunction(self.func):
                        if not await self.func(e):
                            return False
                    else:
                        if not self.func(e):
                            return False
                return True
        return False

    def __str__(self):
        parts = [f"{self.element.__name__}"]
        if self.func is not None:
            parts.append(f"func={self.func.__name__}")
        return f"Exist({', '.join(parts)})"


class Count(Expectation):
    """
    匹配消息链中消息元素的数量。

    :param element: 消息元素类型
    :param eq: 预期匹配精确数量
    :param ge: 预期匹配最小数量
    :param le: 预期匹配最大数量
    """

    def __init__(
        self, element: type[MultimodalElement], eq: int | None = None, ge: int | None = None, le: int | None = None
    ):
        self.element = element
        self.eq = eq
        self.ge = ge
        self.le = le

    async def match(self, result):
        output = result.get("output") or []
        count = 0

        for e in output:
            if isinstance(e, self.element):
                count += 1

        if self.eq is not None and count != self.eq:
            return False
        if self.ge is not None and count < self.ge:
            return False
        if self.le is not None and count > self.le:
            return False
        return True

    def __str__(self):
        parts = [f"{self.element.__name__}"]
        if self.eq is not None:
            parts.append(f"eq={self.eq}")
        if self.ge is not None:
            parts.append(f"ge={self.ge}")
        if self.le is not None:
            parts.append(f"le={self.le}")
        return f"Count({', '.join(parts)})"


class InOrder(Expectation):
    """
    按顺序匹配消息链中的消息元素。

    :param elements: 消息元素类型，可以是多个类型或包含类型的 list/tuple。
    :param consecutive: 是否严格匹配，不允许插入干扰元素。（默认 False）
    """

    def __init__(
        self,
        *elements: type[MultimodalElement] | list[type[MultimodalElement]] | tuple[type[MultimodalElement], ...],
        consecutive: bool = False,
    ):
        if len(elements) == 1 and isinstance(elements[0], (list, tuple)):
            elements = tuple(elements[0])
        self.elements = tuple(elements)
        self.consecutive = consecutive

    async def match(self, result):
        output = result.get("output") or []

        if not self.consecutive:
            last_index = -1
            for e in self.elements:
                matched = False
                for i in range(last_index + 1, len(output)):
                    if isinstance(output[i], e):
                        last_index = i
                        matched = True
                        break
                if not matched:
                    return False
            return True

        n = len(self.elements)
        m = len(output)

        if n == 0:
            return True
        if n > m:
            return False

        for start in range(m - n + 1):
            all_match = True
            for offset, e in enumerate(self.elements):
                if not isinstance(output[start + offset], e):
                    all_match = False
                    break
            if all_match:
                return True
        return False

    def __str__(self):
        return f"InOrder([{', '.join(e.__name__ for e in self.elements)}], consecutive={self.consecutive})"


class StructureEqual(Expectation):
    """
    严格匹配消息链中的消息元素。

    :param elements: 消息元素类型，可以是多个类型或包含类型的 list/tuple。
    """

    def __init__(
        self, *elements: type[MultimodalElement] | list[type[MultimodalElement]] | tuple[type[MultimodalElement], ...]
    ):
        if len(elements) == 1 and isinstance(elements[0], (list, tuple)):
            elements = tuple(elements[0])
        self.elements = tuple(elements)

    async def match(self, result):
        output = result.get("output") or []

        if len(output) != len(self.elements):
            return False

        for e, item in zip(self.elements, output):
            if not isinstance(item, e):
                return False
        return True

    def __str__(self):
        return f"StructureEqual([{', '.join(e.__name__ for e in self.elements)}])"


class Raise(Expectation):
    """
    检查抛出的异常。

    :param exc: 异常类型
    :param message_contain: 期望异常消息包含的字符串
    :param case_sensitive: 是否大小写敏感，默认 False
    """

    def __init__(self, exc: type[Exception], message_contain: str | None = None, case_sensitive: bool = False):
        self.exc_type: type[Exception] = exc
        self.message_contain = message_contain
        self.case_sensitive = case_sensitive

    async def match(self, result):
        exc_instance = result.get("exception")
        if not exc_instance:
            return False

        if not isinstance(exc_instance, self.exc_type):
            return False

        if self.message_contain is not None:
            message_contain = self.message_contain
            exception_message = result.get("exception_message", "")
            if not self.case_sensitive:
                message_contain = message_contain.lower()
                exception_message = exception_message.lower()
            if message_contain not in exception_message:
                return False

        return True

    def __str__(self):
        if self.message_contain is not None:
            return f"Raise({self.exc_type.__name__}, message_contain={self.message_contain!r}, case_sensitive={
                self.case_sensitive
            })"
        return f"Raise({self.exc_type.__name__})"


class Predicate(Expectation):
    """
    自定义期望匹配器。

    :param func: 自定义函数
    """

    def __init__(self, func: Callable):
        self.func = func

    async def match(self, result):
        if asyncio.iscoroutinefunction(self.func):
            return bool(await self.func(result))
        return bool(self.func(result))

    def __str__(self):
        return f"Predicate({self.func.__name__})"
