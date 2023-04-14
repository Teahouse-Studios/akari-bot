from core.dirty_check import check_bool
from core.builtins import Bot
from core.component import module
from modules.ask.agent import agent_executor
from langchain.callbacks import get_openai_callback
from decimal import Decimal

from core.exceptions import NoReportException

ONE_K = Decimal('1000')
# https://openai.com/pricing
BASE_COST_GPT_3_5 = Decimal('0.002') # gpt-3.5-turbo： $0.002 / 1K tokens
THIRD_PARTY_MULTIPLIER = Decimal('1.5') # We are not tracking specific tool usage like searches b/c I'm too lazy, use a universal multiplier
PROFIT_MULTIPLIER = Decimal('1.1') # At the time we are really just trying to break even
PRICE_PER_1K_TOKEN = BASE_COST_GPT_3_5 * THIRD_PARTY_MULTIPLIER * PROFIT_MULTIPLIER
# Assuming 1 USD = 7 CNY, 100 petal = 1 CNY
USD_TO_CNY = 7
CNY_TO_PETAL = 100

a = module('ask', developers=['Dianliang233'], desc='{ask.help.desc}', required_superuser=True)


@a.command('<question> {{ask.help}}')
@a.regex(r'^(?:ask|问)[\:：]? ?(.+?)[?？]$')
async def _(msg: Bot.MessageSession):
    is_superuser =msg.checkSuperUser()
    if not is_superuser and msg.data.petal < 100: # refuse
        raise NoReportException(msg.locale.t('petal_'))
    if hasattr(msg, 'parsed_msg'):
        question = msg.parsed_msg['<question>']
    else:
        question = msg.matched_msg[0]
    if await check_bool(question):
        raise NoReportException('https://wdf.ink/6OUp')
    with get_openai_callback() as cb:
        res = await agent_executor.arun(question)
        tokens = cb.total_tokens
    # TODO: REMEMBER TO UNCOMMENT THIS BEFORE LAUNCH!!!!
    # if not is_superuser:
    #     price = tokens / ONE_K * PRICE_PER_1K_TOKEN
    #     petal = price * USD_TO_CNY * CNY_TO_PETAL
    #     await msg.data.modify_petal(-petal)
    price = tokens / ONE_K * PRICE_PER_1K_TOKEN
    petal = price * USD_TO_CNY * CNY_TO_PETAL
    msg.data.modify_petal(-int(petal))
    if await check_bool(res):
        raise NoReportException('https://wdf.ink/6OUp')
    await msg.finish(res)
