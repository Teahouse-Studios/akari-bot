from pathlib import Path
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

import yaml

instructions_path = Path(__file__).parent / "assets" / "instructions.txt"
if instructions_path.exists():
    with open(instructions_path, "r", encoding="utf-8") as f:
        INSTRUCTIONS = f.read()
else:
    INSTRUCTIONS = ""

llm_api_list_path = next(
    (
        Path(__file__).parent / "assets" / f"llm_api_list{dot_yaml}"
        for dot_yaml in (".yaml", ".yml")
        if (Path(__file__).parent / "assets" / f"llm_api_list{dot_yaml}").exists()
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


llm_list = [llm["name"].lower() for llm in llm_api_list if not llm.get("superuser", False)]
llm_su_list = [llm["name"].lower() for llm in llm_api_list if llm.get("superuser", False)]
