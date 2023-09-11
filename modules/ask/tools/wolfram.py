from langchain.utilities import WolframAlphaAPIWrapper

from config import Config
from .utils import to_async_func, AkariTool

appid = Config('wolfram_alpha_appid')

if appid:
    wolfram = WolframAlphaAPIWrapper(wolfram_alpha_appid=appid)

    async def wolfram_alpha(query: str):
        return await to_async_func(wolfram.run)(query)

    wolfram_tool = AkariTool.from_function(
        func=wolfram_alpha,
        description='A wrapper around Wolfram Alpha. ALWAYS USE THIS TOOL when you need to answer questions about MATH, Science, Technology, Culture, Society and Everyday Life. Also useful for generating SHA or MD5 hashes. Input should be a search query in English.'
    )
else:
    wolfram_tool = None
