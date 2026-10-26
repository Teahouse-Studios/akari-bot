"""modules.ai Python 沙箱图片回传单元测试。"""

import base64
import importlib
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import orjson

from core.tester import func_case, Tester

execute_module = importlib.import_module("modules.ai.tools.execute_python_code")
tools_module = importlib.import_module("modules.ai.tools")
endpoints = importlib.import_module("modules.ai.endpoints")

PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\npng").decode("utf-8")
JPEG_B64 = base64.b64encode(b"\xff\xd8\xff\xe0jpeg").decode("utf-8")


class _FakeSandbox:
    def __init__(self, execution):
        self.execution = execution

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def run_code(self, code, timeout=10):
        return self.execution


def _fake_execution(results):
    return SimpleNamespace(
        error=None,
        results=results,
        logs=SimpleNamespace(stdout=["out"], stderr=["err"]),
    )


async def _test_execute_python_code_returns_images():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        execution = _fake_execution(
            [
                SimpleNamespace(png=PNG_B64, jpeg=None, text="text result"),
                SimpleNamespace(png=None, jpeg=JPEG_B64, text=None),
            ]
        )

        async def _create(**kwargs):
            return _FakeSandbox(execution)

        with (
            patch.object(execute_module, "AsyncSandbox", SimpleNamespace(create=_create)),
            patch.object(execute_module, "random_cache_path", side_effect=lambda: root / str(uuid.uuid4())),
        ):
            result = await execute_module.execute_python_code("print(1)")

        payload = orjson.loads(result)
        images = payload["images"]
        assert [image["data_url"].split(",", maxsplit=1)[0] for image in images] == [
            "data:image/png;base64",
            "data:image/jpeg;base64",
        ]
        assert payload["returns"][0].startswith("[KE:image,path=")
        assert payload["returns"][1] == "text result"
        assert payload["returns"][2].startswith("[KE:image,path=")
        assert payload["stdout"] == ["out", "err"]
        assert all(Path(image["path"]).is_file() for image in images)
        assert Path(images[0]["path"]).read_bytes() == base64.b64decode(PNG_B64)
        assert Path(images[1]["path"]).read_bytes() == base64.b64decode(JPEG_B64)
    return True


async def _test_tool_calls_split_images_into_user_message():
    images = [{"path": "/cache/a.png", "data_url": "data:image/png;base64,AAAA"}]
    result = orjson.dumps({"returns": ["[KE:image,path=/cache/a.png]", "text"], "stdout": [], "images": images}).decode(
        "utf-8"
    )
    tool_call = SimpleNamespace(id="call_1", name="execute_python_code", arguments={"code": "print(1)"})

    messages = [{"role": "assistant", "content": "", "tool_calls": []}]
    with patch.object(tools_module, "execute_python_code", new=AsyncMock(return_value=result)):
        messages = await tools_module.tool_function_calls([tool_call], messages)

    assert [message["role"] for message in messages[-2:]] == ["tool", "user"]
    tool_message = messages[-2]
    assert tool_message["tool_call_id"] == "call_1"
    assert "images" not in orjson.loads(tool_message["content"])

    image_message = messages[-1]
    assert image_message["content"][1] == {"type": "text", "text": "[KE:image,path=/cache/a.png]"}
    assert image_message["content"][2] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    return True


async def _test_parallel_tool_calls_append_single_image_message():
    def _result(index):
        images = [{"path": f"/cache/{index}.png", "data_url": f"data:image/png;base64,AAAA{index}"}]
        return orjson.dumps({"returns": [], "stdout": [], "images": images}).decode("utf-8")

    tool_calls = [
        SimpleNamespace(id=f"call_{index}", name="execute_python_code", arguments={"code": "print(1)"})
        for index in (1, 2)
    ]
    with patch.object(tools_module, "execute_python_code", new=AsyncMock(side_effect=[_result(1), _result(2)])):
        messages = await tools_module.tool_function_calls(tool_calls, [])

    assert [message["role"] for message in messages] == ["tool", "tool", "user"]
    image_parts = [part for part in messages[-1]["content"] if part.get("type") == "image_url"]
    assert len(image_parts) == 2
    return True


def _test_anthropic_merges_image_message_into_tool_turn():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": [{"type": "text", "text": "draw"}]},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "execute_python_code", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "done"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "images"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        },
    ]

    system, converted = endpoints._messages_to_anthropic(messages)

    assert system == "sys"
    assert [message["role"] for message in converted] == ["user", "assistant", "user"]
    assert [block["type"] for block in converted[1]["content"]] == ["tool_use"]
    assert [block["type"] for block in converted[2]["content"]] == ["tool_result", "text", "image"]
    assert converted[2]["content"][2]["source"] == {"type": "base64", "media_type": "image/png", "data": "AAAA"}
    return True


@func_case
async def test_ai_python_images(tester: Tester):
    """modules.ai: 沙箱图片回传与上下文历史测试"""
    await tester.test(_test_execute_python_code_returns_images, "沙箱结果返回图片元数据")
    await tester.test(_test_tool_calls_split_images_into_user_message, "工具结果拆出图片并追加用户消息")
    await tester.test(_test_parallel_tool_calls_append_single_image_message, "并行工具结果合并为一则图片消息")
    await tester.test(_test_anthropic_merges_image_message_into_tool_turn, "Anthropic 合并图片消息到同一轮")
    return tester
