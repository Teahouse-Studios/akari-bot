from langchain.agents import AgentExecutor
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.callbacks import StdOutCallbackHandler
from langchain.chat_models import ChatOpenAI

from config import Config
from modules.ask.prompt import system_message
from modules.ask.tools import tools

llm = ChatOpenAI(
    model='gpt-3.5-turbo-0613',
    temperature=0,
    openai_api_key=Config('openai_api_key'),
    model_kwargs={
        'frequency_penalty': 0.0,
        'presence_penalty': 0.0})


agent = OpenAIFunctionsAgent.from_llm_and_tools(
    llm=llm,
    tools=tools,
    callback_manager=[StdOutCallbackHandler],
    system_message=system_message)

agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)
