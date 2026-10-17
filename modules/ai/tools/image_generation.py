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
            "Use when the user asks to create, draw, or design an image.",
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
            "Use when the user asks to modify, restyle, or change an image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "A precise description of the changes to make to the image.",
                    },
                    "image_index": {
                        "type": "integer",
                        "description": "1-based index of the target image in chronological order. "
                        "Defaults to the most recent image.",
                        "minimum": 1,
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
    image_index: int | None = None,
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
        index = int(image_index) if image_index is not None else len(context.images)
    except (TypeError, ValueError):
        return "Invalid image_index."
    if index < 1 or index > len(context.images):
        return f"Invalid image_index: {len(context.images)} image(s) available."
    client = _build_client(context)
    if client is None:
        return "Image editing is not configured."
    try:
        raw, mime, extension = _decode_image_data_url(context.images[index - 1])
    except Exception as e:
        return f"Unable to read the image: {e}"
    size = _normalize_parameter(size)
    quality = _normalize_parameter(quality)
    enhanced = await _enhance_prompt(context, prompt, "edit")
    kwargs = {
        "prompt": enhanced,
        "image": (f"image{extension}", raw, mime),
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
