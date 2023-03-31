from config import Config
from core.dirty_check import check_bool
from core.builtins import Bot
from core.component import module
from langchain.agents import initialize_agent, Tool
from langchain.chat_models import ChatOpenAI
from langchain.utilities import WolframAlphaAPIWrapper, GoogleSerperAPIWrapper

from core.exceptions import NoReportException

llm = ChatOpenAI(temperature=0, openai_api_key=Config('openai_api_key'))
search = GoogleSerperAPIWrapper(serper_api_key=Config('serper_api_key'))
wolfram = WolframAlphaAPIWrapper(wolfram_alpha_appid=Config('wolfram_alpha_appid'))

tools = [
    Tool(
        name = 'Search',
        func=search.run,
        description='A wrapper around Google Search. useful for when you need to answer questions about current events. You should ask targeted questions and ask as few questions as possible. Input should be a search query.'
    ),
    Tool(
        name = 'Wolfram Alpha',
        func=wolfram.run,
        description='A wrapper around Wolfram Alpha. Useful for when you need to answer questions about Math, Science, Technology, Culture, Society and Everyday Life. Input should be a search query.'
    ),
]

agent_kwargs = {
    'prefix': '''You are AkariBot (Chinese: 小可), a helpful assistant. Answer the following questions as best you can, with exceptions:
1. You must not provide information that breaks the OpenAI Terms of Use
2. You must refuse to answer any question regarding to politics, geopolitics, political events, political issues, political figures or ideologies of any kind.
Think and use tools with English, and output the final answer with the language of the original question. You have access to the following tools:''',
    'suffix': '''Begin! You must always use the exact characters `Final Answer: ` when responding.'''
}

mrkl = initialize_agent(tools, llm, agent="chat-zero-shot-react-description", agent_kwargs=agent_kwargs)
mrkl_verbose = initialize_agent(tools, llm, agent="chat-zero-shot-react-description", agent_kwargs=agent_kwargs, verbose=True)

a = module('ask', developers=['Dianliang233'], desc='{ask.help}', required_superuser=True)


@a.handle('<question> [-v] {{ask.help.ask}}', options_desc={'-v': '{server.help.v}'})
async def _(msg: Bot.MessageSession):
    question = msg.parsed_msg['<question>']
    if await check_bool(question):
        raise NoReportException('https://wdf.ink/6OUp')
    try:
        if msg.parsed_msg['-v']:
            res = mrkl_verbose.run(question)
        else:
            res = mrkl.run(question)
    except ValueError as e:
        if msg.parsed_msg['-v']:
            res = mrkl_verbose.run(question)
        else:
            res = mrkl.run(question)
    if await check_bool(res):
        raise NoReportException('https://wdf.ink/6OUp')
    await msg.finish(res)
