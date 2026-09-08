from pathlib import Path

import yaml

instructions_path = Path(__file__).parent / "assets" / "instructions.txt"
if instructions_path.exists():
    with open(instructions_path, "r", encoding="utf-8") as f:
        INSTRUCTIONS = f.read()
else:
    INSTRUCTIONS = ""

llm_api_list_path = next(
    (
        Path(__file__).parent / "assets" / filename
        for filename in ("llm_api_list.yaml", "llm_api_list.yml")
        if (Path(__file__).parent / "assets" / filename).exists()
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
    if not llm.get("price_in"):
        llm["price_in"] = 0
    if not llm.get("price_out"):
        llm["price_out"] = 0

_name_count = {}
for llm in llm_api_list:
    name = llm["name"]
    _name_count[name] = _name_count.get(name, 0) + 1

_llm_api_list = []
for llm in llm_api_list:
    if _name_count[llm["name"]] == 1:
        _llm_api_list.append(llm)

llm_api_list = _llm_api_list

llm_list = [llm["name"].lower() for llm in llm_api_list if not llm.get("superuser", False)]
llm_su_list = [llm["name"].lower() for llm in llm_api_list if llm.get("superuser", False)]
