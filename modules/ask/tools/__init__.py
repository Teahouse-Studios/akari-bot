from .search import search_tool
from .wolfram import wolfram_tool
from .ip_whois import ip_whois_tool
from .mcv import mcv_tool
from .server import server_tool
from .meme import meme_tool

tools = [
    search_tool,
    wolfram_tool,
    ip_whois_tool,
    mcv_tool,
    server_tool,
    meme_tool
]

tool_names = [tool.name for tool in tools]

__all__ = ['tools', 'tool_names']
