from pathlib import Path
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from string import Template

import yaml

from core.constants.path import module_data_path
from .config import AiConfig

ai_module_path = Path(__file__).parent
ai_data_path = module_data_path(ai_module_path)


class _InstructionsTemplate(Template):
    # 指令文本含 LaTeX 的 $$，标准 Template 会把它折叠成 $；该模式只识别 ${name}，其余 $ 原样保留。
    pattern = r"\$\{(?P<braced>[_a-z][_a-z0-9]*)\}|(?P<named>(?!))|(?P<escaped>(?!))|(?P<invalid>(?!))"


instructions_path = ai_data_path / "instructions.txt"
if instructions_path.exists():
    with open(instructions_path, "r", encoding="utf-8") as f:
        INSTRUCTIONS = _InstructionsTemplate(f.read())
else:
    INSTRUCTIONS = _InstructionsTemplate("")

persona_path = ai_data_path / "persona.txt"
if persona_path.exists():
    with open(persona_path, "r", encoding="utf-8") as f:
        PERSONA = f.read()
else:
    PERSONA = ""

llm_api_list_path = next(
    (
        ai_data_path / f"llm_api_list{dot_yaml}"
        for dot_yaml in (".yaml", ".yml")
        if (ai_data_path / f"llm_api_list{dot_yaml}").exists()
    ),
    None,
)
if llm_api_list_path:
    with open(llm_api_list_path, "r", encoding="utf-8") as f:
        llm_api_list = (yaml.safe_load(f) or {}).get("llm_api_list", [])
else:
    llm_api_list = []

for llm in llm_api_list:
    if not llm.get("name"):
        llm["name"] = llm["model_name"]
    if not llm.get("endpoint"):
        llm["endpoint"] = "openai"
    if not llm.get("price_in"):
        llm["price_in"] = 0
    if not llm.get("price_out"):
        llm["price_out"] = 0
    if not llm.get("price_cache_read"):
        llm["price_cache_read"] = 0
    if not llm.get("price_cache_write"):
        llm["price_cache_write"] = 0

_name_count = {}
for llm in llm_api_list:
    name = llm["name"]
    _name_count[name] = _name_count.get(name, 0) + 1

_llm_api_list = []
for llm in llm_api_list:
    if _name_count[llm["name"]] == 1:
        _llm_api_list.append(llm)

llm_api_list = _llm_api_list


def get_llm_billing(llm: dict, context_tokens: int = 0, now: datetime | None = None) -> dict:
    billing = llm.get("billing") if isinstance(llm.get("billing"), dict) else {}
    billing_type = billing.get("type", "token")
    if billing_type not in {"token", "per_call", "hybrid"}:
        billing_type = "token"

    def safe_price(value) -> int | float:
        try:
            price = Decimal(str(value))
            return value if price.is_finite() and price >= 0 else 0
        except (InvalidOperation, TypeError, ValueError):
            return 0

    prices = {
        "input_price": safe_price(billing.get("price_in", llm.get("price_in", 0))),
        "output_price": safe_price(billing.get("price_out", llm.get("price_out", 0))),
        "cache_read_price": safe_price(billing.get("price_cache_read", llm.get("price_cache_read", 0))),
        "cache_write_price": safe_price(billing.get("price_cache_write", llm.get("price_cache_write", 0))),
        "call_price": safe_price(billing.get("call_price", 0)),
    }
    if billing_type == "per_call":
        prices["input_price"] = prices["cache_write_price"] = prices["cache_read_price"] = 0
        prices["output_price"] = 0

    tiers = billing.get("tiers")
    time_rules = billing.get("time_rules")
    use_tiers = isinstance(tiers, list) and bool(tiers) and not (isinstance(time_rules, list) and time_rules)
    use_time_rules = isinstance(time_rules, list) and bool(time_rules) and not (isinstance(tiers, list) and tiers)

    if billing_type != "per_call" and use_tiers:
        valid_tiers = [
            tier
            for tier in tiers
            if isinstance(tier, dict)
            and isinstance(tier.get("context_threshold"), int)
            and tier["context_threshold"] >= 0
        ]
        if len(valid_tiers) == len(tiers):
            tier = max(
                (tier for tier in valid_tiers if tier["context_threshold"] <= context_tokens),
                key=lambda item: item["context_threshold"],
                default=None,
            )
            if tier:
                for price_name, config_name in (
                    ("input_price", "price_in"),
                    ("cache_write_price", "price_cache_write"),
                    ("cache_read_price", "price_cache_read"),
                    ("output_price", "price_out"),
                ):
                    if config_name in tier:
                        prices[price_name] = safe_price(tier[config_name])

    if billing_type != "per_call" and use_time_rules:
        current = now or datetime.now()
        if current.tzinfo is not None:
            current = current.astimezone()
        current_time = current.time()
        for rule in time_rules:
            if not isinstance(rule, dict) or not isinstance(rule.get("time_range"), str):
                continue
            try:
                start_text, end_text = rule["time_range"].split("-", 1)
                start = time.fromisoformat(start_text)
                end = time.fromisoformat(end_text)
                weeks = rule.get("week", list(range(1, 8)))
                if not isinstance(weeks, list) or current.isoweekday() not in weeks:
                    continue
                in_range = (
                    start <= current_time <= end if start <= end else current_time >= start or current_time <= end
                )
                if in_range:
                    for price_name, config_name in (
                        ("input_price", "price_in"),
                        ("cache_write_price", "price_cache_write"),
                        ("cache_read_price", "price_cache_read"),
                        ("output_price", "price_out"),
                    ):
                        if config_name in rule:
                            prices[price_name] = safe_price(rule[config_name])
                    break
            except (TypeError, ValueError):
                continue

    return prices


def get_llm_generation(llm: dict) -> dict:
    """返回模型自定义的生成参数。

    采样参数显式设为 null 时会被保留，供端点在调用时省略对应请求字段；
    未配置的键不会出现，由端点在调用时回落到模块默认值。

    :param llm: 模型配置。
    :return: temperature、top_p、top_logprobs、reasoning_effort 中已配置项的字典。
    """
    generation = {key: llm[key] for key in ("temperature", "top_p", "top_logprobs") if key in llm}
    reasoning_effort = llm.get("reasoning_effort")
    if reasoning_effort is not None:
        generation["reasoning_effort"] = reasoning_effort
    return generation


llm_list = [llm["name"].lower() for llm in llm_api_list if not llm.get("superuser", False)]
llm_su_list = [llm["name"].lower() for llm in llm_api_list if llm.get("superuser", False)]

# 配置的默认模型可能已从 llm_api_list 中移除，只有仍可用时才作为默认值。
default_llm = AiConfig.ai_default_llm if AiConfig.ai_default_llm in llm_list else None
