from types import SimpleNamespace

from unittest.mock import AsyncMock, patch

from core.builtins.bot import Bot
from core.loader import ModulesManager
from core.tester import ContainsAll, Tester, func_case
from modules.wiki.utils.wikilib import WikiInfo, WikiLib, WikiStatus

API = "https://zh.minecraft.wiki/api.php"


@func_case
async def test_wiki_diff_entries(tester: Tester):
    info = WikiInfo(
        api=API,
        script="https://zh.minecraft.wiki/",
        articlepath="https://zh.minecraft.wiki/w/$1",
        realurl="https://zh.minecraft.wiki",
        name="Minecraft Wiki",
        is_allowed=True,
    )

    async def fixup(wiki):
        wiki.wiki_info = info

    async def background(session, factory, **kwargs):
        await factory()

    modules = ModulesManager.return_modules_list()
    with (
        patch.object(
            ModulesManager, "return_modules_list", return_value={key: modules[key] for key in ("wiki", "wiki-inline")}
        ),
        patch.object(WikiLib, "fixup_wiki_info", new=fixup),
        patch.object(
            WikiLib, "check_wiki_info_from_database_cache", new=AsyncMock(return_value=WikiStatus(True, info, ""))
        ),
        patch.object(WikiLib, "check_wiki_available", new=AsyncMock(return_value=WikiStatus(True, info, ""))),
        patch(
            "modules.wiki.wiki.WikiTargetInfo.get_by_target_id",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    api_link=API,
                    headers={},
                    interwikis={},
                    prefix=None,
                )
            ),
        ),
        patch("modules.wiki.wiki._start_background_with_release", new=background),
        patch("modules.wiki.inline._start_background_with_release", new=background),
        patch.object(Bot.Info, "web_render_status", False),
    ):
        for value in [
            "~wiki Special:Diff/1495502",
            "[[Special:Diff/1495502]]",
            "https://zh.minecraft.wiki/w/Special:Diff/1495502",
            "https://zh.minecraft.wiki/?diff=1495502&variant=zh-cn",
        ]:
            await tester.integrate(value, ContainsAll("1494706", "1495502", "Module:NameProvider/snapshot"), value)
        for value in [
            "https://zh.minecraft.wiki/w/%E5%88%BB?curid=7766&diff=1500031&oldid=1476854",
            "~wiki 刻&diff=1500031&oldid=1476854",
        ]:
            await tester.integrate(value, ContainsAll("刻", "1476854", "1500031"), value)
    return tester
