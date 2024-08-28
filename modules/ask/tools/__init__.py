from .bugtracker import bugtracker_tool
from .ip_whois import ip_whois_tool
from .mcv import mcv_tool
from .meme import meme_tool
from .random import random_choice_tool, random_number_tool, random_uuid_tool
from .search import search_tool
from .self_knowledge import self_knowledge_tool
from .server import server_tool
from .wolfram import wolfram_tool

tools = [
    search_tool,
    ip_whois_tool,
    mcv_tool,
    server_tool,
    meme_tool,
    random_choice_tool,
    random_number_tool,
    random_uuid_tool,
    bugtracker_tool,
    self_knowledge_tool
]

if wolfram_tool:
    tools.append(wolfram_tool)

tool_names = [tool.name for tool in tools]

__all__ = ['tools', 'tool_names']
