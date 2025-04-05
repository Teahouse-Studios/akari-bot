import os

import orjson as json

from core.constants.path import assets_path

ai_assets_path = os.path.join(assets_path, "modules", "ai")

instructions_path = os.path.join(ai_assets_path, "instructions.txt")
if os.path.exists(instructions_path):
    with open(instructions_path, "r", encoding="utf-8") as f:
        INSTRUCTIONS = f.read()
else:
    INSTRUCTIONS = ""

llm_api_list_path = os.path.join(ai_assets_path, "llm_api_list.json")
if os.path.exists(llm_api_list_path):
    with open(llm_api_list_path, "r") as f:
        llm_api_list = json.loads(f.read()).get("llm_api_list", [])
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
