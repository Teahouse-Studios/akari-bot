from langchain.utilities.duckduckgo_search import DuckDuckGoSearchAPIWrapper

from .utils import to_async_func, AkariTool

search = DuckDuckGoSearchAPIWrapper()


async def search(query: str):
    return to_async_func(search.run)(query)

search_tool = AkariTool.from_function(
    func=search,
    description='DuckDuckGo Search. Useful for when you need to answer questions about current events. You should ask targeted questions and ask as few questions as possible.'
)
