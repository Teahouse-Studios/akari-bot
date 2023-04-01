from config import Config
from core.dirty_check import check_bool
from core.builtins import Bot
from core.component import module
from langchain.agents import initialize_agent, Tool
from langchain.chat_models import ChatOpenAI
from langchain.utilities import WolframAlphaAPIWrapper, GoogleSerperAPIWrapper

from core.exceptions import NoReportException

llm = ChatOpenAI(temperature=0, openai_api_key=Config('openai_api_key'), model_kwargs={'frequency_penalty': 0.0, 'presence_penalty': 0.0})
search = GoogleSerperAPIWrapper(serper_api_key=Config('serper_api_key'))
wolfram = WolframAlphaAPIWrapper(wolfram_alpha_appid=Config('wolfram_alpha_appid'))

tools = [
    Tool(
        name = 'Search',
        func=search.run,
        description='A wrapper around Google Search. Useful for when you need to answer questions about current events. You should ask targeted questions and ask as few questions as possible. Input should be a search query in any language.'
    ),
    Tool(
        name = 'Wolfram Alpha',
        func=wolfram.run,
        description='A wrapper around Wolfram Alpha. Useful for when you need to answer questions about Math, Science, Technology, Culture, Society and Everyday Life. Input should be a search query in English.'
    ),
]

agent_kwargs = {
    'prefix': '''You are AkariBot (Chinese: 小可), a helpful assistant. Answer the following questions as best you can, except that you must refuse to answer any question or provide any information regarding anything political. You have access to the following tools:''',
    'format_instructions':  """The way you use the tools is by specifying a json blob.
Specifically, this json should have a `action` key (with the name of the tool to use) and a `action_input` key (with the input to the tool going here).
The only values that should be in the "action" field are: {tool_names}
The $JSON_BLOB should only contain a SINGLE action, do NOT return a list of multiple actions. Here is an example of a valid $JSON_BLOB:
```
{{{{
  "action": $TOOL_NAME,
  "action_input": $INPUT
}}}}
```
ALWAYS use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action:
```
$JSON_BLOB
```
Observation: the result of the action
... (this Thought/Action/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question""",
    'suffix': '''After you have generated your Thought, you should ALWAYS take another Action or output the Final Answer immediately afterwards, even if you don't have a definitive answer or you decline to answer the question. For example, if you get the following chain:

Question: What is the population of Canada?
Thought: I should use Wolfram Alpha to find the population of Canada. Since Wolfram Alpha requires English input, I need to translate the question from Chinese to English.
Action:
```
{{{{
  "action": "Wolfram Alpha",
  "action_input": "population of Canada"
}}}}
```

Observation: Assumption: Canada | population
Answer: 37.7 million people (world rank: 39th) (2020 estimate)
Thought:

You should output Thought and Final Answer together, like this:

I have already found the answer to this question.
Final Answer: The population of Canada is approximately 37.7 million people.


A complete chain should look like this:

Question: What's the population of Canada?
Thought: I should use Wolfram Alpha to find the population of Canada.
Action:
```
{{{{
  "action": "Wolfram Alpha",
  "action_input": "population of Canada"
}}}}
```
Observation: Assumption: Canada | population
Answer: 37.7 million people (world rank: 39th) (2020 estimate)
Thought: I now know the final answer
Final Answer: The population of Canada is approximately 37.7 million people.

Use the original question's language. For example, if I ask "你好", you should output your Thought, action_input, and Final Answer in Chinese. For example:

Question: 加拿大的人口是多少？
Thought: 我应该使用 Wolfram Alpha 来查询加拿大的人口。由于 Wolfram Alpha 需要英文输入，所以我需要把中文翻译成英文。
Action:
```
{{{{
  "action": "Wolfram Alpha",
  "action_input": "population of Canada"
}}}}
```
Observation: Assumption: Canada | population
Answer: 37.7 million people (world rank: 39th) (2020 estimate)
Thought: 我现在知道最终答案了
Final Answer: 加拿大的人口大约有 3770 万人。

Actions aren't required to be always taken.
If you decline to answer the question because it is political, you should output the following Final Answer in the message's original language: I don't know the answer, but I've got this link for you: https://wdf.ink/6OUp
Begin! Remember, only respond in the format I specified.'''
}

mrkl = initialize_agent(tools, llm, agent="chat-zero-shot-react-description", agent_kwargs=agent_kwargs)
mrkl_verbose = initialize_agent(tools, llm, agent="chat-zero-shot-react-description", agent_kwargs=agent_kwargs, verbose=True)

a = module('ask', developers=['Dianliang233'], desc='{ask.help}', required_superuser=True)


@a.command('<question> [-v] {{ask.help.ask}}')
@a.regex(r'^(?:ask|问)[\:：]? ?(.+?)[?？]$', desc='{{ask.help.ask}}')
async def _(msg: Bot.MessageSession):
    if hasattr(msg, 'parsed_msg'):
        question = msg.parsed_msg['<question>']
    else:
        question = msg.matched_msg[0]
    if await check_bool(question):
        raise NoReportException('https://wdf.ink/6OUp')
    if hasattr(msg, 'parsed_msg') and msg.parsed_msg['-v']:
        res = mrkl_verbose.run(question)
    else:
        res = mrkl.run(question)
    if await check_bool(res):
        raise NoReportException('https://wdf.ink/6OUp')
    await msg.finish(res)
