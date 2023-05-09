from core.builtins import Bot
from core.component import module

f = module('factor', developers=[
    'DoroWolf'], desc='{factor.help.desc}', required_superuser=True)

@f.handle('prime <number> {{factor.help.prime}}')
async def prime(msg: Bot.MessageSession):
    number = msg.parsed_msg.get('<number>')
    n=int(number)
    i=2
    primes_list=[]
    if number<=1:
        await msg.finish('{factor.message.prime.invalid}')
    while i<=n:
        if n%i==0:
            list.append(str(i))
            n=n//i
        else:
            i+=1
    prime="*".join(primes_list)
    await msg.finish(f"{number}={prime}")
