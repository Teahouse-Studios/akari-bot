import urllib.parse

import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser
from core.utils import get_url

api = 'https://ca.projectxero.top/idlist/search'


async def auto_search(ctx: discord.AutocompleteContext):
    title = ctx.options["keywords"]
    query_options = {'q': title, 'limit': '5'}
    query_url = api + '?' + urllib.parse.urlencode(query_options)
    resp = await get_url(query_url, 200, fmt='json')
    result_ = resp['data']['result']
    results = []
    if result_:
        for x in result_:
            results.append(f'{x["enumName"]} {x["key"]}')
    return results


@client.slash_command(description="查询MCBEID表")
@discord.option(name="keywords", description="关键词", autocomplete=auto_search)
async def idlist(ctx: discord.ApplicationContext, keywords: str):
    await slash_parser(ctx, keywords)
