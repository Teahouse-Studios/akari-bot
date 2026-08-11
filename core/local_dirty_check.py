import asyncio
import re
import threading
from pathlib import Path
from typing import Any

from core.logger import Logger

SAFETY_PATTERN = re.compile(r"Safety:\s*(Safe|Unsafe|Controversial)", re.IGNORECASE)
CATEGORY_PATTERN = re.compile(
    r"Violent|Non-violent Illegal Acts|Sexual Content or Sexual Acts|PII|Suicide & Self-Harm|"
    r"Unethical Acts|Politically Sensitive Topics|Copyright Violation|Jailbreak|None",
    re.IGNORECASE,
)

_model_lock = threading.RLock()
_model: Any = None
_tokenizer: Any = None
_loaded_model_name: str | None = None


def extract_label_and_categories(content: str) -> tuple[str | None, list[str]]:
    label_match = SAFETY_PATTERN.search(content)
    label = label_match.group(1).title() if label_match else None
    categories = [match.group(0) for match in CATEGORY_PATTERN.finditer(content)]
    return label, categories


def resolve_model_path(model_name: str) -> str:
    local_path = Path(model_name).expanduser()
    if local_path.exists():
        return str(local_path)

    try:
        from modelscope import snapshot_download
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "ModelScope is required to resolve a model ID. Run `uv sync --extra local-dirty-check` first."
        ) from exc
    try:
        return snapshot_download(model_name, local_files_only=True)
    except Exception:
        return snapshot_download(model_name)


def _load_model(model_name: str):
    global _loaded_model_name, _model, _tokenizer

    if _model is not None and _tokenizer is not None and _loaded_model_name == model_name:
        return _tokenizer, _model

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        raise RuntimeError(
            "Failed to import the local dirty check runtime. Run `uv sync --extra local-dirty-check`; "
            "if it is already installed, reinstall the package named in the original exception."
        ) from exc

    model_path = resolve_model_path(model_name)
    Logger.info(f"Loading local dirty check model: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path, dtype="auto", device_map="auto")
    model.eval()

    _tokenizer = tokenizer
    _model = model
    _loaded_model_name = model_name
    return tokenizer, model


def _moderate_sync(texts: list[str], model_name: str, max_new_tokens: int) -> list[dict]:
    results = []
    with _model_lock:
        tokenizer, model = _load_model(model_name)
        for prompt in texts:
            text = tokenizer.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False)
            model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
            generated_ids = model.generate(**model_inputs, max_new_tokens=max_new_tokens, do_sample=False)
            output_ids = generated_ids[0][len(model_inputs.input_ids[0]) :].tolist()
            content = tokenizer.decode(output_ids, skip_special_tokens=True)
            Logger.debug("Output Content: " + content)
            label, categories = extract_label_and_categories(content)
            if label is None:
                raise ValueError(f"Failed to parse Qwen3Guard response: {content!r}")
            results.append({"label": label, "categories": categories, "raw": content})
    return results


async def moderate(texts: list[str], model_name: str, max_new_tokens: int = 128) -> list[dict]:
    return await asyncio.to_thread(_moderate_sync, texts, model_name, max_new_tokens)


__all__ = ["extract_label_and_categories", "moderate", "resolve_model_path"]
