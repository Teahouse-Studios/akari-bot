from core.tester import All, Match, Contains, Regex, Tester, func_case
from core.loader import ModulesManager
from unittest.mock import patch
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from modules.wiki.utils.magic import _REGISTRY_CACHE

START_WIKI = "~wiki set https://zh.minecraft.wiki/api.php"


@func_case
async def test_wiki_magic_commands(tester: Tester):
    _REGISTRY_CACHE.clear()
    await tester.integrate(START_WIKI, Contains("成功设置默认 Wiki"), "绑定查询站点")
    for command, expected in [
        ("~wiki magic {{#expr:2 * 3 + 4}}", Match("10")),
        ("~wiki magic #expr:2*3+4", Match("10")),
        ('~wiki magic {{PAGENAME}} -p "Help:Some page"', Match("Some page")),
        ("~wiki {{SITENAME}}", Match("Minecraft Wiki")),
        ("~wiki {{#expr:2*3+4}}", Match("10")),
        ("~wiki {{#if:1| magic |none}}", Match("magic")),
        ("~wiki magic {{PAGENAME}}", Contains("需要页面上下文")),
        ("~wiki magic {{#expr:1/0}}", Contains("求值失败")),
        ("~wiki magic {{#invoke:Example|main}}", Contains("未支持")),
        ("~wiki magic {{#if:1|{{Infobox}}|}}", Contains("未支持")),
    ]:
        await tester.integrate(command, expected, command)
    return tester


@func_case
async def test_wiki_magic_inline(tester: Tester):
    _REGISTRY_CACHE.clear()
    await tester.integrate(START_WIKI, Contains("成功设置默认 Wiki"), "绑定内联查询站点")
    await tester.integrate(["~module enable wiki-inline", "是"], Contains("wiki-inline"), "启用 Wiki 内联查询")
    modules = ModulesManager.return_modules_list()
    cases = [
        ("{{#expr:2*3+4}}", Match("10")),
        ("{{站点名称}}", Match("Minecraft Wiki")),
        ("{{#计算式:2*3+4}}", Match("10")),
        ("{{完整URL:石头}}", Contains("https://zh.minecraft.wiki/w/")),
        ("{{#if:1|{{#expr:2*3+4}}|0}}", Match("10")),
        ("{{PAGENAME}}", Contains("需要页面上下文")),
        ("{{SITENAME}} {{CURRENTYEAR}}", All(Contains("SITENAME = Minecraft Wiki"), Regex(r"CURRENTYEAR = \d{4}"))),
    ]
    with patch.object(
        ModulesManager, "return_modules_list", return_value={key: modules[key] for key in ("wiki", "wiki-inline")}
    ):
        for command, expected in cases:
            await tester.integrate(command, expected, command)

        async def template_query(msg, titles, **kwargs):
            assert kwargs["template"] is True
            message = kwargs.get("preset_message") or MessageChain.create()
            message.append(Plain("Template:" + titles[0]))
            await msg.finish(message)

        with patch("modules.wiki.wiki.query_pages", new=template_query):
            for command, expected in [
                ("{{Infobox|name={{SITENAME}}}}", Match("Template:Infobox")),
                ("{{Template:SITENAME}}", Match("Template:SITENAME")),
                ("~wiki {{Template:SITENAME}}", Match("Template:SITENAME")),
                ("{{SITENAME}} {{Infobox}}", All(Contains("Minecraft Wiki"), Contains("Template:Infobox"))),
            ]:
                await tester.integrate(command, expected, command)

        async def page_query(msg, title, **kwargs):
            assert title == "List of magic words" and kwargs["lang"] == "en"
            await msg.finish(Plain(title))

        with patch("modules.wiki.wiki.query_pages", new=page_query):
            await tester.integrate(
                "~wiki List of magic words -l en", Match("List of magic words"), "页名中的 magic 保持普通查询"
            )
    return tester
