import os

from core.constants.path import assets_path

ai_assets_path = os.path.join(assets_path, "modules", "ai")

chatgpt_llms_path = os.path.join(ai_assets_path, "chatgpt_llms.txt")
if os.path.exists(chatgpt_llms_path):
    with open(chatgpt_llms_path, "r", encoding="utf-8") as f:
        chatgpt_llms = [llm.strip().lower() for llm in f if llm.strip()]
else:
    chatgpt_llms = []

claude_llms_path = os.path.join(ai_assets_path, "claude_llms.txt")
if os.path.exists(claude_llms_path):
    with open(claude_llms_path, "r", encoding="utf-8") as f:
        claude_llms = [llm.strip().lower() for llm in f if llm.strip()]
else:
    claude_llms = []

deepseek_llms_path = os.path.join(ai_assets_path, "deepseek_llms.txt")
if os.path.exists(deepseek_llms_path):
    with open(deepseek_llms_path, "r", encoding="utf-8") as f:
        deepseek_llms = [llm.strip().lower() for llm in f if llm.strip()]
else:
    deepseek_llms = []


avaliable_llms = chatgpt_llms + claude_llms + deepseek_llms
visible_llms = [llm for llm in avaliable_llms if not llm.startswith("!")]
