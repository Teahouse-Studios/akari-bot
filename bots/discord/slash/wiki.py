import re

import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser, ctx_to_session
from modules.wiki import WikiLib, WikiTargetInfo


@client.slash_command(description="Get recent abuse logs for the default wiki.")
async def ab(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@client.slash_command(description="Get recent newbie logs for the default wiki.")
async def newbie(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


@client.slash_command(description="Get recent changes for the default wiki.")
async def rc(ctx: discord.ApplicationContext):
    await slash_parser(ctx, "")


wiki = client.create_group("wiki", "Query information from Mediawiki-based websites.")


async def auto_search(ctx: discord.AutocompleteContext):
    title = ctx.options["pagename"]
    iw = ''
    target = WikiTargetInfo(ctx_to_session(ctx))
    iws = target.get_interwikis()
    query_wiki = target.get_start_wiki()
    if match_iw := re.match(r'(.*?):(.*)', title):
        if match_iw.group(1) in iws:
            query_wiki = iws[match_iw.group(1)]
            iw = match_iw.group(1) + ':'
            title = match_iw.group(2)
    if not query_wiki:
        return []
    wiki = WikiLib(query_wiki)
    if title != "":
        return [iw + x for x in (await wiki.search_page(title))]
    else:
        return [
            iw + (await wiki.get_json(action='query', list='random', rnnamespace='0'))['query']['random'][0]['title']]


async def auto_get_custom_iw_list(ctx: discord.AutocompleteContext):
    target = WikiTargetInfo(ctx_to_session(ctx)).get_interwikis()
    if not target:
        return []
    else:
        return list(target.keys())


async def default_wiki(ctx: discord.AutocompleteContext):
    if not ctx.options["wikiurl"]:
        return ['https://zh.minecraft.wiki/']


@wiki.command(name="query", description="Query a wiki page.")
@discord.option(name="pagename", description="The title of wiki page.", autocomplete=auto_search)
@discord.option(name="lang", description="Find the corresponding language version of this page.")
async def query(ctx: discord.ApplicationContext, pagename: str, lang: str = None):
    if lang:
        await slash_parser(ctx, f'{pagename} -l {lang}')
    else:
        await slash_parser(ctx, pagename)


@wiki.command(name="id", description="Query a Wiki page based on page ID.")
@discord.option(name="pageid", description="The wiki page ID.")
@discord.option(name="lang", description="Find the corresponding language version of this page.")
async def byid(ctx: discord.ApplicationContext, pageid: str, lang: str = None):
    if lang:
        await slash_parser(ctx, f'id {pageid} -l {lang}')
    else:
        await slash_parser(ctx, f'id {pageid}')


@wiki.command(name="search", description="Search a wiki page.")
@discord.option(name="pagename", description="The title of wiki page.", autocomplete=auto_search)
async def search(ctx: discord.ApplicationContext, pagename: str):
    await slash_parser(ctx, f'search {pagename}')


@wiki.command(name="set", description="Set up start wiki.")
@discord.option(name="wikiurl", description="The URL of wiki.", autocomplete=default_wiki)
async def set_base(ctx: discord.ApplicationContext, wikiurl: str):
    await slash_parser(ctx, f'set {wikiurl}')


iw = wiki.create_subgroup("iw", "Set up commands for custom Interwiki.")


@iw.command(name="add", description="Add custom Interwiki.")
@discord.option(name="interwiki", description="The custom Interwiki.")
@discord.option(name="wikiurl", description="The URL of wiki.")
async def add(ctx: discord.ApplicationContext, interwiki: str, wikiurl: str):
    await slash_parser(ctx, f'iw add {interwiki} {wikiurl}')


@iw.command(name="remove", description="Remove custom Interwiki.")
@discord.option(name="interwiki", description="The custom Interwiki.", autocomplete=auto_get_custom_iw_list)
async def iwremove(ctx: discord.ApplicationContext, interwiki: str):
    await slash_parser(ctx, f'iw remove {interwiki}')


@iw.command(name="list", description="Lists the currently configured Interwiki.")
@discord.option(name="legacy", choices=['false', 'true'], description="Whether to use legacy mode.")
async def iw_list(ctx: discord.ApplicationContext, legacy: str):
    legacy = "-l" if legacy == "true" else ""
    await slash_parser(ctx, f'iw list {legacy}')


@iw.command(name="get", description="Get the API address corresponding to the set Interwiki.")
@discord.option(name="interwiki", description="The custom Interwiki.", autocomplete=auto_get_custom_iw_list)
async def get(ctx: discord.ApplicationContext, interwiki: str):
    await slash_parser(ctx, f'iw get {interwiki}')


headers = wiki.create_subgroup("headers", "Set up commands for custom response headers.")


@headers.command(name="add", description="Add custom request headers.")
@discord.option(name="headers", description="The json of custom request headers.")
async def add_headers(ctx: discord.ApplicationContext, headers: str):
    await slash_parser(ctx, f'headers set {headers}')


@headers.command(name="remove", description="Remove custom request headers.")
@discord.option(name="headerkey", description="The key of custom request headers json.")
async def set_headers(ctx: discord.ApplicationContext, headerkey: str):
    await slash_parser(ctx, f'headers remove {headerkey}')


@headers.command(name='show', description="View the currently set request headers.")
async def show_headers(ctx: discord.ApplicationContext):
    await slash_parser(ctx, 'headers show')


@headers.command(name='reset', description="Reset custom request headers.")
async def reset_headers(ctx: discord.ApplicationContext):
    await slash_parser(ctx, 'headers reset')


p = wiki.create_subgroup("prefix", "Set up commands for custom wiki prefix.")


@p.command(name="set", description="Set custom wiki prefix.")
@discord.option(name="prefix", description="The custom wiki prefix.")
async def set_prefix(ctx: discord.ApplicationContext, prefix: str):
    await slash_parser(ctx, f'prefix set {prefix}')


@p.command(name="reset", description="Reset custom wiki prefix.")
async def reset_prefix(ctx: discord.ApplicationContext):
    await slash_parser(ctx, 'prefix reset')


@wiki.command(name="fandom", description="Toggle whether to use Fandom global Interwiki queries.")
async def fandom(ctx: discord.ApplicationContext):
    await slash_parser(ctx, 'fandom')


@wiki.command(name="redlink", description="Toggle whether to return the edit link when the page does not exist.")
async def redlink(ctx: discord.ApplicationContext):
    await slash_parser(ctx, 'redlink')
