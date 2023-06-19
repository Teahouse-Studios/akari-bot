from langchain.utilities.duckduckgo_search import DuckDuckGoSearchAPIWrapper

from .utils import to_async_func, AkariTool

search = DuckDuckGoSearchAPIWrapper()


search_tool = AkariTool(
    name='Search',
    func=to_async_func(search.run),
    description='A wrapper around DuckDuckGo Search. Useful for when you need to answer questions about current events. You should ask targeted questions and ask as few questions as possible. You can perform up to 3 queries, so do not search with the same keyword. Input should be a search query in any language.'
)
