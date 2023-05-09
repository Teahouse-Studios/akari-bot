import asyncio

from core.builtins import Bot
from core.component import module
from core.exceptions import NoReportException
from core.logger import Logger

factor = module('factor', developers=[
    'DoroWolf'], desc='{factor.help.desc}', required_superuser=True)

@c.handle('prime <number> {{factor.help.prime}}')
async def prime(msg: Bot.MessageSession):
    number = msg.parsed_msg.get('<number>')
    n=number
    i=2
    primes_list=[]
    if num<=1:
        await msg.finish('{factor.message.prime.invalid}')
    while i<=n:
        if n%i==0:
            list.append(str(i))
            n=n//i
        else:
            i+=1
    prime="*".join(primes_list)
    await msg.finish(f"{number}={prime}")