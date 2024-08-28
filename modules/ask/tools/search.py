from langchain.utilities.duckduckgo_search import DuckDuckGoSearchAPIWrapper

from .utils import to_async_func, AkariTool

ddg = DuckDuckGoSearchAPIWrapper()


async def search(query: str):
    return await to_async_func(ddg.run)(query)


search_tool = AkariTool.from_function(
    func=search,
    description='DuckDuckGo Search. Useful for when you need to answer questions about current events. You should ask targeted questions and ask as few questions as possible.'
)
