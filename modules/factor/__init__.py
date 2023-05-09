import time

from core.builtins import Bot
from core.component import module

factor = module('factor', developers=[
    'DoroWolf'], desc='{factor.help.desc}', required_superuser=True)

@factor.handle('prime <number> {{factor.prime.help}}')
async def prime(msg: Bot.MessageSession):
    number = int(msg.parsed_msg.get('<number>'))
    start_time = time.time()
    n = number
    i = 2
    primes_list = []
    if number <= 1:
        await msg.finish(msg.locale.t('factor.prime.message.error.invalid'))
    while i <= n:
        if n % i == 0:
            primes_list.append(str(i))
            n = n // i
        else:
            i += 1
    prime="*".join(primes_list)
    if len(primes_list) == 1:
        await msg.finish(msg.locale.t('factor.prime.message.is_prime'))
    else:
        await msg.finish(f"{number}={prime}")
    running_time = time.time() - start_time
    if running_time > 10:
        await msg.finish(msg.locale.t('factor.prime.message.error.time_out'))
