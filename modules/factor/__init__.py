import time

from core.builtins import Bot
from core.component import module

factor = module('factor', developers=[
    'DoroWolf'], desc='{factor.help.desc}')

@factor.handle('prime <number> {{factor.prime.help}}')
async def prime(msg: Bot.MessageSession):
    number_str = msg.parsed_msg.get('<number>')
    number = int(number_str)
    start_time = time.time()
    n = number
    i = 2
    loopcnt = 0
    primes_list = []
    if number <= 1 or not number_str.isdigit():
        await msg.finish(msg.locale.t('factor.prime.message.error'))
    while i <= n:
        loopcnt += 1
        if not(loopcnt % 100):
            if time.time() - start_time >= 10:
                await msg.finish(msg.locale.t('factor.message.time_out'))
        if n % i:
            i += 1
        else:
            n //= i
            primes_list.append(str(i))
    prime="*".join(primes_list)
    end_time = time.time()
    running_time = end_time - start_time
    if len(primes_list) == 1:
        result = msg.locale.t("factor.prime.message.is_prime", num=number)
    else:
        result = f"{number} = {prime}"
    checkpermisson = msg.checkSuperUser()
    if checkpermisson:
        result += '\n' + msg.locale.t("factor.message.running_time", time=f"{running_time:.2f}")
    await msg.finish(result)
