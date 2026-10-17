"""modules.ai 图片生成与编辑工具单元测试。"""

import base64
from contextlib import ExitStack
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import orjson

from core.i18n import Locale
from core.tester import Tester, func_case
from modules.ai import image_prompt, llm, setting
from modules.ai import petal as petal_module
from modules.ai.tools import image_generation
from modules.ai.tools.context import ToolContext

IMAGE_CONFIG = {
    "model_name": "gpt-image-1",
    "base_url": "https://img.example/v1",
    "api_key": "img-key",
    "costs": {},
}


class _FakeImageElement:
    @classmethod
    def assign(cls, _path):
        return cls()

    async def get(self):
        return "/cache/generated.png"

    async def get_base64(self, mime=False):
        return "data:image/png;base64,AAAA"


class _FakeImages:
    def __init__(self):
        self.generate = AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(b64_json="AAAA", url=None)]))
        self.edit = AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(b64_json="AAAA", url=None)]))


class _FakeClientFactory:
    def __init__(self):
        self.images = _FakeImages()
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(images=self.images)


class _FakePromptEngineer:
    def __init__(self):
        self.calls = []

    async def enhance(self, prompt, mode):
        self.calls.append((prompt, mode))
        return f"enhanced:{prompt}"


class _FailingPromptEngineer:
    async def enhance(self, prompt, mode):
        raise RuntimeError("prompt engineering failed")


def _data_url(raw: bytes) -> str:
    return f"data:image/png;base64,{base64.b64encode(raw).decode()}"


def _patched_image_environment(factory, cost=Decimal("7")):
    stack = ExitStack()
    stack.enter_context(patch.object(image_generation, "image_api", IMAGE_CONFIG))
    stack.enter_context(patch.object(image_generation, "AsyncOpenAI", factory))
    stack.enter_context(patch.object(image_generation, "ImageElement", _FakeImageElement))
    stack.enter_context(patch.object(image_generation, "CoreConfig", SimpleNamespace(enable_petal=True)))
    stack.enter_context(patch.object(image_generation, "get_image_cost", lambda size, quality: cost))
    return stack


def _test_image_cost_lookup():
    costs = {
        "1024x1024:high": 16,
        "high": 12,
        "1024x1024": 8,
        "default": 4,
        "auto": 6,
        "low": 2,
    }
    with patch.object(setting, "image_api", {"costs": costs}):
        assert setting.get_image_cost("1024x1024", "high") == Decimal("16")
        assert setting.get_image_cost(None, "high") == Decimal("12")
        assert setting.get_image_cost("1024x1024", None) == Decimal("8")
        assert setting.get_image_cost(None, None) == Decimal("4")
        assert setting.get_image_cost("999x999", "ultra") == Decimal("4")
    with patch.object(setting, "image_api", {"costs": 5}):
        assert setting.get_image_cost() == Decimal("5")
    with patch.object(setting, "image_api", {"costs": {"default": -3}}):
        assert setting.get_image_cost() == Decimal("0")
    return True


async def _test_generate_image_uses_enhanced_prompt_and_charges():
    factory = _FakeClientFactory()
    engineer = _FakePromptEngineer()
    context = ToolContext(api_key="chat-key", api_url="https://chat.example/v1", prompt_engineer=engineer)
    with _patched_image_environment(factory):
        result = await image_generation.generate_image("a cat", "1024x1024", "high", context=context)

    payload = orjson.loads(result)
    assert payload["returns"] == ["[KE:image,path=/cache/generated.png]"]
    assert payload["images"] == [{"path": "/cache/generated.png", "data_url": "data:image/png;base64,AAAA"}]
    assert factory.images.generate.await_args.kwargs == {
        "model": "gpt-image-1",
        "prompt": "enhanced:a cat",
        "n": 1,
        "size": "1024x1024",
        "quality": "high",
    }
    assert factory.kwargs == {
        "api_key": "img-key",
        "timeout": 120,
        "base_url": "https://img.example/v1",
    }
    assert engineer.calls == [("a cat", "generate")]
    assert context.cost == Decimal("7")
    return True


async def _test_edit_image_uses_latest_image_and_charges():
    factory = _FakeClientFactory()
    engineer = _FakePromptEngineer()
    first = _data_url(b"first")
    second = _data_url(b"second")
    context = ToolContext(images=[first, second], prompt_engineer=engineer)
    with _patched_image_environment(factory):
        result = await image_generation.edit_image("make it blue", context=context)

    payload = orjson.loads(result)
    assert payload["returns"] == ["[KE:image,path=/cache/generated.png]"]
    assert factory.images.edit.await_args.kwargs == {
        "model": "gpt-image-1",
        "prompt": "enhanced:make it blue",
        "image": ("image.png", b"second", "image/png"),
    }
    assert engineer.calls == [("make it blue", "edit")]
    assert context.cost == Decimal("7")
    return True


async def _test_edit_image_rejects_missing_or_invalid_image():
    factory = _FakeClientFactory()
    with _patched_image_environment(factory):
        no_image = await image_generation.edit_image("make it blue", context=ToolContext())
        out_of_range = await image_generation.edit_image(
            "make it blue", image_index=2, context=ToolContext(images=[_data_url(b"only")])
        )
    assert "No image" in no_image
    assert "Invalid image_index" in out_of_range
    factory.images.edit.assert_not_awaited()
    return True


async def _test_generate_image_falls_back_to_raw_prompt_and_does_not_charge_on_failure():
    factory = _FakeClientFactory()
    context = ToolContext(prompt_engineer=_FailingPromptEngineer())
    logger = SimpleNamespace(exception=Mock())
    with _patched_image_environment(factory), patch.object(image_generation, "Logger", logger):
        await image_generation.generate_image("a cat", context=context)

    assert factory.images.generate.await_args.kwargs["prompt"] == "a cat"
    assert context.cost == Decimal("7")

    failing_factory = _FakeClientFactory()
    failing_factory.images.generate = AsyncMock(side_effect=RuntimeError("bad request"))
    failing_context = ToolContext()
    with _patched_image_environment(failing_factory), patch.object(image_generation, "Logger", logger):
        error = await image_generation.generate_image("a cat", context=failing_context)

    assert "Unable to generate image" in error
    assert failing_context.cost == Decimal("0")
    return True


async def _test_prompt_engineer_uses_current_endpoint_and_counts_usage():
    class _FakeEndpoint:
        def __init__(self):
            self.calls = []

        async def create(self, messages, tool_choice=None):
            self.calls.append((messages, tool_choice))
            return SimpleNamespace(
                text='"A detailed prompt."',
                input_tokens=2,
                output_tokens=3,
                cache_read_tokens=4,
                cache_write_tokens=5,
            )

    endpoint = _FakeEndpoint()
    engineer = image_prompt.ImagePromptEngineer(endpoint)
    result = await engineer.enhance("draw a cat", "generate")

    assert result == "A detailed prompt."
    messages, tool_choice = endpoint.calls[0]
    assert tool_choice == "none"
    assert messages[0]["content"] == image_prompt.IMAGE_GENERATION_PROMPT_SYSTEM
    assert messages[1] == {"role": "user", "content": "draw a cat"}
    assert (engineer.input_tokens, engineer.output_tokens) == (2, 3)
    assert (engineer.cache_read_tokens, engineer.cache_write_tokens) == (4, 5)

    await engineer.enhance("remove the hat", "edit")
    assert endpoint.calls[1][0][0]["content"] == image_prompt.IMAGE_EDIT_PROMPT_SYSTEM
    return True


async def _test_extra_cost_is_converted_to_petals():
    sender = SimpleNamespace(petal=100, modify_petal=AsyncMock())
    session_info = SimpleNamespace(superuser=False, sender_union_info=sender)
    with (
        patch.object(petal_module, "CoreConfig", SimpleNamespace(enable_petal=True)),
        patch.object(petal_module, "cost_to_petal", Decimal("2")),
    ):
        charged = await petal_module.count_token_petal(session_info, 0, 0, 0, 0, 0, 0, 0, 0, extra_cost=Decimal("2.6"))

    assert charged == 6
    sender.modify_petal.assert_awaited_once_with(-6)
    assert session_info.petal == 100
    return True


async def _test_tool_dispatch_passes_context_and_splits_images():
    from modules.ai import tools

    context = ToolContext(images=[_data_url(b"only")])
    messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": context.images[0]}}]}]
    tool_call = SimpleNamespace(id="call_1", name="generate_image", arguments={"prompt": "a cat"})
    generated = orjson.dumps(
        {
            "returns": ["[KE:image,path=/cache/generated.png]"],
            "images": [{"path": "/cache/generated.png", "data_url": "data:image/png;base64,AAAA"}],
        }
    ).decode()
    with patch.object(tools, "generate_image", AsyncMock(return_value=generated)):
        messages = await tools.tool_function_calls([tool_call], messages, context=context)

    assert [message["role"] for message in messages[-2:]] == ["tool", "user"]
    assert orjson.loads(messages[-2]["content"]) == {"returns": ["[KE:image,path=/cache/generated.png]"]}
    assert messages[-1]["content"][1] == {"type": "text", "text": "[KE:image,path=/cache/generated.png]"}
    return True


async def _test_ask_llm_returns_accumulated_image_cost():
    endpoint = SimpleNamespace(calls=0)

    async def create(messages, tool_choice=None):
        endpoint.calls += 1
        if endpoint.calls == 1:
            return SimpleNamespace(
                text="",
                tool_calls=[SimpleNamespace(id="call_1", name="generate_image", arguments={"prompt": "cat"})],
                input_tokens=1,
                output_tokens=2,
                cache_read_tokens=0,
                cache_write_tokens=0,
                assistant_message={
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "generate_image"}}],
                },
            )
        return SimpleNamespace(
            text="done",
            tool_calls=[],
            input_tokens=3,
            output_tokens=4,
            cache_read_tokens=0,
            cache_write_tokens=0,
            assistant_message={"role": "assistant", "content": "done"},
        )

    endpoint.create = create

    async def fake_tool_calls(tool_calls, messages, context=None):
        context.cost = Decimal("9")
        messages.append({"role": "tool", "tool_call_id": "call_1", "content": "ok"})
        return messages

    session_info = SimpleNamespace(
        locale=Locale("zh_cn"),
        _tz_offset="+0",
        sender_union_info=SimpleNamespace(sender_data={}),
        support_markdown=False,
        support_markdown_extension=False,
        support_image=False,
        require_check_dirty_words=False,
        superuser=False,
    )
    with (
        patch.object(llm, "build_endpoint", lambda *args, **kwargs: endpoint),
        patch.object(llm, "tool_function_calls", fake_tool_calls),
        patch.object(llm, "check", AsyncMock(side_effect=lambda response, session=None: [{"content": response}])),
    ):
        result = await llm.ask_llm(SimpleNamespace(session_info=session_info), "draw a cat", "m", "u", "k")

    assert result[6] == Decimal("9")
    return True


@func_case
async def test_ai_image_generation(tester: Tester):
    """modules.ai: 图片生成与编辑工具、提示工程与成本折算测试"""
    await tester.test(_test_image_cost_lookup, "按尺寸与品质查找图片成本")
    await tester.test(_test_generate_image_uses_enhanced_prompt_and_charges, "生图使用增强提示并记录成本")
    await tester.test(_test_edit_image_uses_latest_image_and_charges, "编辑默认使用最近一张图片")
    await tester.test(_test_edit_image_rejects_missing_or_invalid_image, "编辑拒绝缺失或越界图片")
    await tester.test(
        _test_generate_image_falls_back_to_raw_prompt_and_does_not_charge_on_failure,
        "提示工程失败回退且生图失败不计成本",
    )
    await tester.test(_test_prompt_engineer_uses_current_endpoint_and_counts_usage, "提示工程复用当前端点")
    await tester.test(_test_extra_cost_is_converted_to_petals, "图片成本按比率折算并入总扣费")
    await tester.test(_test_tool_dispatch_passes_context_and_splits_images, "工具分发传入上下文并拆分图片")
    await tester.test(_test_ask_llm_returns_accumulated_image_cost, "ask_llm 回传图片成本")
    return tester
