from aiohttp import ClientSession
from core.dirty_check import check_bool
from core.builtins import Bot
from core.component import module
from modules.ask.agent import agent_executor

from core.exceptions import NoReportException

a = module('ask', developers=['Dianliang233'], desc='{ask.help.desc}', required_superuser=True)


@a.command('<question> {{ask.help}}')
@a.regex(r'^(?:ask|问)[\:：]? ?(.+?)[?？]$')
async def _(msg: Bot.MessageSession):
    if hasattr(msg, 'parsed_msg'):
        question = msg.parsed_msg['<question>']
    else:
        question = msg.matched_msg[0]
    if await check_bool(question):
        raise NoReportException('https://wdf.ink/6OUp')
    async with ClientSession() as session:
        res = await agent_executor.arun(question)
    if await check_bool(res):
        raise NoReportException('https://wdf.ink/6OUp')
    await msg.finish(res)
