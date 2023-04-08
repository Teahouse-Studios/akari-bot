import ujson as json
from typing import Callable

from langchain.agents import Tool
from langchain.utilities import WolframAlphaAPIWrapper, GoogleSerperAPIWrapper

from core.utils.i18n import Locale
from core.types.message import MessageSession, MsgInfo, Session
from config import Config
from modules.mcv import mcv, mcbv, mcdv, mcev
from modules.server import server
from modules.whois.ip import check_ip
from modules.meme.moegirl import moegirl
from modules.meme.nbnhhsh import nbnhhsh
from modules.meme.urban import urban


search = GoogleSerperAPIWrapper(serper_api_key=Config('serper_api_key'))
wolfram = WolframAlphaAPIWrapper(wolfram_alpha_appid=Config('wolfram_alpha_appid'))


def to_json_func(func: Callable):
    async def wrapper(*args, **kwargs):
        return json.dumps(await func(*args, **kwargs))
    return wrapper

def to_async_func(func: Callable):
    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

def with_args(func: Callable, *args, **kwargs):
    async def wrapper(*a, **k):
        # if a is tuple with empty string
        if len(a) == 1 and a[0] == '':
            return await func(*args, **kwargs, **k)
        return await func(*args, *a, **kwargs, **k)
    return wrapper

class AkariTool(Tool):
    def __init__(self, name: str, func: Callable, description: str = None):
        super().__init__(name, func, description)
        self.coroutine = func

fake_msg = MessageSession(MsgInfo('Ask|0', 'Ask|0', 'AkariBot', 'Ask', 'Ask', 'Ask', 0),
                          Session('~lol lol', 'Ask|0', 'Ask|0'))
fake_msg.locale = Locale('en_us')

tools = [
    AkariTool(
        name = 'Search',
        func=to_async_func(search.run),
        description='A wrapper around Google Search. Useful for when you need to answer questions about current events. You should ask targeted questions and ask as few questions as possible. You can perform up to 3 queries, so do not search with the same keyword. Input should be a search query in any language.'
    ),
    AkariTool(
        name = 'Wolfram Alpha',
        func=to_async_func(wolfram.run),
        description='A wrapper around Wolfram Alpha. Useful for when you need to answer questions about Math, Science, Technology, Culture, Society and Everyday Life. Also useful for generating SHA or MD5 hashes. Input should be a search query in English.'
    ),
    AkariTool(
        name = 'IP WHOIS',
        func=to_json_func(check_ip),
        description='A WHOIS tool for IP addresses. Useful for when you need to answer questions about IP addresses. Input should be a valid IP address. Output is a JSON document.'
    ),
    AkariTool(
        name = 'Minecraft: Java Edition Version',
        func=with_args(mcv, fake_msg),
        description='A tool for checking current Minecraft: Java Edition versions. No input is required.'
    ),
    AkariTool(
        name = 'Minecraft: Bedrock Edition Version',
        func=with_args(mcbv, fake_msg),
        description='A tool for checking current Minecraft: Bedrock Edition versions. No input is required.'
    ),
    AkariTool(
        name = 'Minecraft Dungeons Version',
        func=with_args(mcdv, fake_msg),
        description='A tool for checking current Minecraft Dungeons versions. No input is required.'
    ),
    AkariTool(
        name = 'Minecraft: Education Edition Version',
        func=with_args(mcev, fake_msg),
        description='A tool for checking current Minecraft: Education Edition versions. No input is required.'
    ),
    AkariTool(
        name = 'Minecraft: Java Edition Server',
        funct=with_args(server, fake_msg),
        description='A tool for checking the status of Minecraft: Java Edition servers. Input should be a valid Minecraft server address.'
    ),
    AkariTool(
        name = 'Minecraft: Bedrock Edition Server',
        funct=with_args(server, fake_msg, mode='b'),
        description='A tool for checking the status of Minecraft: Bedrock Edition servers. Input should be a valid Minecraft server address.'
    ),
]

tool_names = [tool.name for tool in tools]

__all__ = ['tools', 'tool_names']
