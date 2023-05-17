from langchain import LLMChain
from langchain.agents import AgentExecutor, LLMSingleActionAgent
from langchain.callbacks.base import CallbackManager
from langchain.callbacks.stdout import StdOutCallbackHandler
from langchain.chat_models import ChatOpenAI

from config import Config
from modules.ask.prompt import AkariPromptTemplate, AkariParser, template
from modules.ask.tools import tools, tool_names

prompt = AkariPromptTemplate(
    template=template,
    tools=tools,
    input_variables=["input", "intermediate_steps"]
)

output_parser = AkariParser()

llm = ChatOpenAI(
    temperature=0,
    openai_api_key=Config('openai_api_key'),
    model_kwargs={
        'frequency_penalty': 0.0,
        'presence_penalty': 0.0})

llm_chain = LLMChain(llm=llm, prompt=prompt)

manager = CallbackManager([StdOutCallbackHandler()])

agent = LLMSingleActionAgent(
    llm_chain=llm_chain,
    output_parser=output_parser,
    stop=["\nObservation:"],
    allowed_tools=tool_names,
)

agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True, callback_manager=manager)
