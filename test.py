from wikim import wikim
import asyncio
loop = asyncio.get_event_loop()
result = loop.run_until_complete(wikim('wiki Netherite'))
print(result)
loop.close()