import orjson

from core.constants.path import assets_path

ai_assets_path = assets_path / "modules" / "ai"

instructions_path = ai_assets_path / "instructions.txt"
if instructions_path.exists():
    with open(instructions_path, "r", encoding="utf-8") as f:
        INSTRUCTIONS = f.read()
else:
    INSTRUCTIONS = ""

llm_api_list_path = ai_assets_path / "llm_api_list.json"
if llm_api_list_path.exists():
    with open(llm_api_list_path, "rb") as f:
        llm_api_list = orjson.loads(f.read()).get("llm_api_list", [])
else:
    llm_api_list = []

for l in llm_api_list:
    if not l.get("name"):
        l["name"] = l["model_name"]
    if not l.get("price_in"):
        l["price_in"] = 0
    if not l.get("price_out"):
        l["price_out"] = 0

_name_count = {}
for l in llm_api_list:
    name = l["name"]
    _name_count[name] = _name_count.get(name, 0) + 1

_llm_api_list = []
for l in llm_api_list:
    if _name_count[l["name"]] == 1:
        _llm_api_list.append(l)

llm_api_list = _llm_api_list

llm_list = [l["name"] for l in llm_api_list if not l.get("superuser", False)]
llm_su_list = [l["name"] for l in llm_api_list if l.get("superuser", False)]
