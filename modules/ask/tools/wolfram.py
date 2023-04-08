from .utils import to_async_func, AkariTool
from config import Config
from langchain.utilities import WolframAlphaAPIWrapper

wolfram = WolframAlphaAPIWrapper(wolfram_alpha_appid=Config('wolfram_alpha_appid'))

wolfram_tool = AkariTool(
    name = 'Wolfram Alpha',
    func=to_async_func(wolfram.run),
    description='A wrapper around Wolfram Alpha. Useful for when you need to answer questions about Math, Science, Technology, Culture, Society and Everyday Life. Also useful for generating SHA or MD5 hashes. Input should be a search query in English.'
)
