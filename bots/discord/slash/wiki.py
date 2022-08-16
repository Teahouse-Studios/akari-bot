import asyncio

import discord

from bots.discord.client import client
from bots.discord.slash_parser import slash_parser


wiki = client.create_group("wiki", "查询Mediawiki的相关信息", guild_ids=[557879624575614986])


@wiki.command(description="根据页面名称查询一个wiki页面")
@discord.option(name="title", description="页面名称")
async def query(ctx: discord.ApplicationContext, title: str):
    await slash_parser(ctx, title)


@wiki.command(description="根据页面名称搜索一个wiki页面")
@discord.option(name="title", description="页面名称")
async def search(ctx: discord.ApplicationContext, title: str):
    await slash_parser(ctx, f'search {title}')


@wiki.command(name="id", description="根据页面ID查询一个wiki页面")
@discord.option(name="pid", description="页面ID")
async def page_id(ctx: discord.ApplicationContext, pid: str):
    await slash_parser(ctx, f'-p {pid}')


@wiki.command(name="set", description="设置起始查询wiki")
@discord.option(name="link", description="页面链接")
async def set_base(ctx: discord.ApplicationContext, link: str):
    await slash_parser(ctx, f'set {link}')


iw = wiki.create_subgroup("iw", "设置有关自定义Interwiki的命令")


@iw.command(description="添加自定义Interwiki")
@discord.option(name="interwiki", description="自定义iw名")
@discord.option(name="link", description="页面链接")
async def add(ctx: discord.ApplicationContext, iw: str, link: str):
    await slash_parser(ctx, f'iw add {iw} {link}')


@iw.command(name='remove',description="删除自定义Interwiki")
@discord.option(name="iw", description="自定义iw名")
async def iw_remove(ctx: discord.ApplicationContext, iw: str):
    await slash_parser(ctx, f'iw rm {iw}')


@iw.command(name="list", description="查看所有已自定义的Interwiki")
async def iw_list(ctx: discord.ApplicationContext):
    await slash_parser(ctx, 'iw list')


@iw.command(description="获取自定义Interwiki的链接")
@discord.option(name="iw", description="自定义interwiki名")
async def get(ctx: discord.ApplicationContext, iw: str):
    await slash_parser(ctx, f'iw get {iw}')


headers = wiki.create_subgroup("headers", "设置有关自定义header的命令")


@headers.command(name="set", description="添加自定义headers")
@discord.option(name="headers_json", description="自定义headers")
async def set_headers(ctx: discord.ApplicationContext, headers_json: str):
    await slash_parser(ctx, f'headers set {headers_json}')


@headers.command(description="删除一个自定义header")
@discord.option(name="header_key")
async def delete(ctx: discord.ApplicationContext, header_key: str):
    await slash_parser(ctx, f'headers del {header_key}')


@headers.command(name='show', description="查看所有自定义的headers")
async def headers_show(ctx: discord.ApplicationContext):
    await slash_parser(ctx, 'headers show')


@headers.command(name='reset', description="重置所有自定义的headers")
async def headers_reset(ctx: discord.ApplicationContext):
    await slash_parser(ctx, 'headers reset')


@wiki.command(description="是否启用Fandom全局Interwiki查询")
@discord.option(name="_", choices=['enable', 'disable'])
async def fandom(ctx: discord.ApplicationContext, _: str):
    await slash_parser(ctx, f'fandom {_}')

