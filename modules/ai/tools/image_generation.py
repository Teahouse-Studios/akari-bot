import base64
import mimetypes

import orjson
from openai import AsyncOpenAI

from core.builtins.message.internal import ImageElement
from core.config.base import CoreConfig
from core.logger import Logger
from ..setting import get_image_cost, image_api
from .context import ToolContext

IMAGE_TIMEOUT = 120


if image_api:
    generate_image_desc = {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate a new image from a description. "
            "Only use when the user asks to create, draw, or design an image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "A detailed description of the image, including subject, composition, "
                        "style, lighting, and colors.",
                    },
                    "size": {
                        "type": "string",
                        "description": "Optional image size such as 1024x1024, 1536x1024, or 1024x1536. "
                        "Supported values depend on the configured model.",
                    },
                    "quality": {
                        "type": "string",
                        "description": "Optional quality preset such as low, medium, high, or auto. "
                        "Supported values depend on the configured model.",
                    },
                },
                "required": ["prompt"],
            },
        },
    }
    edit_image_desc = {
        "type": "function",
        "function": {
            "name": "edit_image",
            "description": "Edit an existing image from the conversation. "
            "Only use when the user asks to modify, restyle, or change an image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "A precise description of the changes to make to the image.",
                    },
                    "image_indexes": {
                        "type": "array",
                        "description": "1-based indexes of the target images in chronological order. "
                        "Defaults to the most recent image. Provide several indexes when the edit "
                        "combines multiple images.",
                        "items": {"type": "integer", "minimum": 1},
                        "minItems": 1,
                    },
                    "size": {
                        "type": "string",
                        "description": "Optional output size such as 1024x1024. "
                        "Supported values depend on the configured model.",
                    },
                    "quality": {
                        "type": "string",
                        "description": "Optional quality preset such as low, medium, high, or auto. "
                        "Supported values depend on the configured model.",
                    },
                },
                "required": ["prompt"],
            },
        },
    }
else:
    generate_image_desc = {}
    edit_image_desc = {}


def _normalize_parameter(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _build_client(context: ToolContext | None) -> AsyncOpenAI | None:
    api_key = image_api.get("api_key") or (context.api_key if context else "")
    base_url = image_api.get("base_url") or (context.api_url if context else "")
    if not image_api.get("model_name") or not api_key:
        return None
    kwargs = {"api_key": api_key, "timeout": IMAGE_TIMEOUT}
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncOpenAI(**kwargs)


async def _enhance_prompt(context: ToolContext | None, prompt: str, mode: str) -> str:
    if context is None or context.prompt_engineer is None:
        return prompt
    try:
        enhanced = await context.prompt_engineer.enhance(prompt, mode)
    except Exception:
        Logger.exception("Image prompt engineering failed, falling back to the original prompt: ")
        return prompt
    return enhanced.strip() or prompt


def _charge_image(context: ToolContext | None, size: str | None, quality: str | None) -> None:
    if context is None or context.superuser or not CoreConfig.enable_petal:
        return
    context.cost += get_image_cost(size, quality)


def _decode_image_data_url(data_url: str) -> tuple[bytes, str, str]:
    header, _, encoded = data_url.partition(",")
    if not header.startswith("data:") or not encoded:
        raise ValueError("Unsupported image data.")
    mime = header.removeprefix("data:").split(";", maxsplit=1)[0] or "image/png"
    extension = mimetypes.guess_extension(mime) or ".png"
    return base64.b64decode(encoded), mime, extension


def _resolve_image_indexes(image_indexes: list[int] | int | None, available: int) -> list[int]:
    if image_indexes is None:
        return [available]
    if isinstance(image_indexes, int):
        image_indexes = [image_indexes]
    if not isinstance(image_indexes, (list, tuple)):
        raise ValueError("Invalid image_indexes.")
    indexes: list[int] = []
    for value in image_indexes:
        try:
            index = int(value)
        except (TypeError, ValueError):
            raise ValueError("Invalid image_indexes.") from None
        if index < 1 or index > available:
            raise ValueError(f"Invalid image_indexes: {available} image(s) available.")
        if index not in indexes:
            indexes.append(index)
    if not indexes:
        raise ValueError("Invalid image_indexes: no image specified.")
    return indexes


def _build_image_files(indexes: list[int], images: list[str]) -> list[tuple[str, bytes, str]]:
    files = []
    for position, index in enumerate(indexes, start=1):
        raw, mime, extension = _decode_image_data_url(images[index - 1])
        filename = f"image{position}{extension}" if len(indexes) > 1 else f"image{extension}"
        files.append((filename, raw, mime))
    return files


async def _image_response_to_tool_result(response) -> str:
    data = getattr(response, "data", None) or []
    if not data:
        return "The image API returned no image data."
    item = data[0]
    b64_json = getattr(item, "b64_json", None)
    url = getattr(item, "url", None)
    if b64_json:
        element = ImageElement.assign(f"data:image/png;base64,{b64_json}")
    elif url:
        element = ImageElement.assign(url)
    else:
        return "The image API returned no image data."
    path = await element.get()
    data_url = await element.get_base64(mime=True)
    payload = {
        "returns": [f"[KE:image,path={path}]"],
        "images": [{"path": path, "data_url": data_url}],
    }
    return orjson.dumps(payload).decode("utf-8")


def _build_request(size: str | None, quality: str | None) -> dict:
    kwargs = {"model": image_api["model_name"]}
    if size:
        kwargs["size"] = size
    if quality:
        kwargs["quality"] = quality
    return kwargs


async def generate_image(
    prompt: str,
    size: str | None = None,
    quality: str | None = None,
    context: ToolContext | None = None,
) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "The image prompt is empty."
    client = _build_client(context)
    if client is None:
        return "Image generation is not configured."
    size = _normalize_parameter(size)
    quality = _normalize_parameter(quality)
    enhanced = await _enhance_prompt(context, prompt, "generate")
    kwargs = {"prompt": enhanced, "n": 1, **_build_request(size, quality)}
    try:
        response = await client.images.generate(**kwargs)
        result = await _image_response_to_tool_result(response)
    except Exception as e:
        Logger.exception("Image generation failed: ")
        return f"Unable to generate image: {e}"
    _charge_image(context, size, quality)
    return result


async def edit_image(
    prompt: str,
    image_indexes: list[int] | int | None = None,
    size: str | None = None,
    quality: str | None = None,
    context: ToolContext | None = None,
) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "The image edit prompt is empty."
    if context is None or not context.images:
        return "No image is available in the conversation."
    try:
        indexes = _resolve_image_indexes(image_indexes, len(context.images))
    except ValueError as e:
        return str(e)
    client = _build_client(context)
    if client is None:
        return "Image editing is not configured."
    try:
        files = _build_image_files(indexes, context.images)
    except Exception as e:
        return f"Unable to read the image: {e}"
    size = _normalize_parameter(size)
    quality = _normalize_parameter(quality)
    enhanced = await _enhance_prompt(context, prompt, "edit")
    kwargs = {
        "prompt": enhanced,
        "image": files[0] if len(files) == 1 else files,
        **_build_request(size, quality),
    }
    try:
        response = await client.images.edit(**kwargs)
        result = await _image_response_to_tool_result(response)
    except Exception as e:
        Logger.exception("Image editing failed: ")
        return f"Unable to edit image: {e}"
    _charge_image(context, size, quality)
    return result


__all__ = [
    "edit_image",
    "edit_image_desc",
    "generate_image",
    "generate_image_desc",
]
