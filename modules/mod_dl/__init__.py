import asyncio
import re

from core.builtins.bot import Bot
from core.builtins.message.internal import Plain, I18NContext
from core.component import module
from core.config import Config
from core.utils.http import get_url
from core.utils.func import is_int

mod_dl = module(
    module_name="mod_dl",
    desc="{I18N:mod_dl.help.desc}",
    doc=True,
    developers=["HornCopper", "OasisAkari", "z0z0r4"],
    recommend_modules=["mcmod"],
    alias="moddl",
)

x_api_key = Config("curseforge_api_key", cfg_type=str, secret=True, table_name="module_mod_dl")
enable_mirror = bool(
    not x_api_key
)  # CurseForge API Key 未配置，使用镜像 https://mcim.z0z0r4.top ...(z0z0r4 不想解析网页)


@mod_dl.command("<mod_name> [<version>] {{I18N:mod_dl.help}}")
async def _(msg: Bot.MessageSession, mod_name: str, version: str = None):
    ver = version
    if version:
        match_ver = re.match(r"^\d+\.\d+\.\d+$|^\d+\.\d+$|\d+w\d+[abcd]", version)
        if not match_ver:
            mod_name += " " + version
            ver = False

    async def search_modrinth(name: str, ver: str):
        url = f"https://api.modrinth.com/v2/search?query={name}&limit=10"
        if ver:
            url += f'&facets=[["versions:{ver}"],["project_type:mod"]]'
        else:
            url += '&facets=[["project_type:mod"]]'
        resp = await get_url(url, 200, fmt="json", timeout=5, attempt=3)
        if resp:
            results = []
            hits = resp.get("hits", [])
            if len(hits) == 0:
                return None
            for project in hits:
                results.append(
                    ("modrinth", project.get("title", ""), project.get("project_id", ""), project.get("versions", []))
                )
            return results

    async def search_curseforge(name: str, ver: str):
        if enable_mirror:
            # https://mcim.z0z0r4.top/docs#/Curseforge/curseforge_search_curseforge_search_get
            url = f"https://mcim.z0z0r4.top/curseforge/search?gameId=432&searchFilter={
                name
            }&sortField=2&sortOrder=desc&pageSize=10&classId=6"
            headers = None
        else:
            headers = {"Accept": "application/json", "x-api-key": x_api_key}
            url = f"https://api.curseforge.com/v1/mods/search?gameId=432&searchFilter={
                name
            }&sortField=2&sortOrder=desc&pageSize=10&classId=6"

        if ver:
            url += f"&gameVersion={ver}"
        results = []
        resp = await get_url(url, 200, fmt="json", timeout=5, attempt=3, headers=headers)
        if resp:
            if not enable_mirror:  # 没提供 pagination
                if resp.get("pagination", {}).get("resultCount", 0) == 0:
                    return None
            for mod in resp.get("data", []):
                results.append(("curseforge", mod.get("name", ""), mod.get("id", ""), None))
        return results

    async def get_modrinth_project_version(project_id: str, ver: str):
        url = f'https://api.modrinth.com/v2/project/{project_id}/version?game_versions=["{ver}"]&featured=true'
        resp_list = await get_url(url, 200, fmt="json", timeout=5, attempt=3)
        if resp_list:
            return resp_list[0]

    async def get_curseforge_mod_version_index(modid: str):
        if enable_mirror:
            # https://mcim.z0z0r4.top/docs#/Curseforge/get_mod_curseforge_mod__modid_slug__get
            url = f"https://mcim.z0z0r4.top/curseforge/mod/{modid}"
            headers = None
        else:
            headers = {"Accept": "application/json", "x-api-key": x_api_key}
            url = f"https://api.curseforge.com/v1/mods/{modid}"
        resp = await get_url(url, 200, fmt="json", timeout=5, attempt=3, headers=headers)
        if resp:
            return resp.get("data", {}).get("latestFilesIndexes", [])

    async def get_curseforge_mod_file(modid: str, ver: str):
        if enable_mirror:
            url = f"https://mcim.z0z0r4.top/curseforge/mod/{modid}/files?gameVersion={ver}"
            headers = None
        else:
            headers = {"Accept": "application/json", "x-api-key": x_api_key}
            url = f"https://api.curseforge.com/v1/mods/{modid}/files?gameVersion={ver}"

        resp = await get_url(url, 200, fmt="json", timeout=5, attempt=3, headers=headers)
        if resp:
            data = resp.get("data", [])
            return data[0] if data else None

    # 搜索 Mod
    result = await asyncio.gather(*(search_modrinth(mod_name, ver), search_curseforge(mod_name, ver)))
    cache_result = []
    if not result[0] and not result[1]:
        await msg.finish(I18NContext("mod_dl.message.not_found"))
    else:
        # 合并搜索结果
        reply_chain = []
        count = 0

        # 先显示 CurseForge 的结果
        if not result[1]:
            reply_chain.append(I18NContext("mod_dl.message.curseforge.not_found"))
        else:
            reply_chain.append(I18NContext("mod_dl.message.curseforge.result"))
            for mod in result[1]:
                count += 1
                reply_chain.append(Plain(f"{count}. {mod[1]}"))
                cache_result.append(mod)

        if not result[0]:
            reply_chain.append(I18NContext("mod_dl.message.modrinth.not_found"))
        reply_chain.append(I18NContext("mod_dl.message.modrinth.result"))
        for mod in result[0]:
            count += 1
            reply_chain.append(Plain(f"{count}. {mod[1]}"))
            cache_result.append(mod)
        reply_chain.append(I18NContext("mod_dl.message.prompt"))

        reply = await msg.wait_reply(reply_chain, delete=True)
        replied = reply.as_display(text_only=True)

        # 查找 Mod
        if is_int(replied):
            replied = int(replied)
            if not replied or replied > len(cache_result):
                await msg.finish(I18NContext("mod_dl.message.invalid.out_of_range"))
            else:
                mod_info = cache_result[replied - 1]
        else:
            await msg.finish(I18NContext("mod_dl.message.invalid.non_digital"))

        if mod_info[0] == "modrinth":  # modrinth mod
            if not ver:
                reply2 = await msg.wait_reply(
                    f"{msg.session_info.locale.t('mod_dl.message.version')}\n"
                    + "\n".join(mod_info[3])
                    + f"\n{msg.session_info.locale.t('mod_dl.message.version.prompt')}",
                    delete=True,
                )
                replied2 = reply2.as_display(text_only=True)
                if replied2 in mod_info[3]:
                    version_info = await get_modrinth_project_version(mod_info[2], replied2)
                    if version_info:
                        files = version_info.get("files", [])
                        if files:
                            await msg.finish(
                                f"{' '.join(version_info.get('loaders', []))}\n{msg.session_info.locale.t('mod_dl.message.download_url')}{files[0].get('url', '')}\n{msg.session_info.locale.t('mod_dl.message.filename')}{files[0].get('filename', '')}"
                            )
                else:
                    await msg.finish()
            elif ver not in mod_info[3]:
                await msg.finish(I18NContext("mod_dl.message.version.not_found"))
            elif ver in mod_info[3]:
                version_info = await get_modrinth_project_version(mod_info[2], ver)
                if version_info:
                    files = version_info.get("files", [])
                    if files:
                        await msg.finish(
                            f"{' '.join(version_info.get('loaders', []))}\n{msg.session_info.locale.t('mod_dl.message.download_url')}{files[0].get('url', '')}\n{msg.session_info.locale.t('mod_dl.message.filename')}{files[0].get('filename', '')}"
                        )
        else:  # curseforge mod
            version_index = await get_curseforge_mod_version_index(mod_info[2]) or []
            ver_list = []
            for version_ in version_index:
                game_version = version_.get("gameVersion", "")
                if game_version not in ver_list:
                    ver_list.append(game_version)
            if version_index:
                if not ver:
                    reply2 = await msg.wait_reply(
                        f"{msg.session_info.locale.t('mod_dl.message.version')}\n"
                        + "\n".join(ver_list)
                        + f"\n{msg.session_info.locale.t('mod_dl.message.version.prompt')}",
                        delete=True,
                    )
                    ver = reply2.as_display(text_only=True)
                elif ver not in ver_list:
                    await msg.finish(I18NContext("mod_dl.message.version.not_found"))

                if ver in ver_list:
                    file_info = await get_curseforge_mod_file(mod_info[2], ver)
                    if file_info:
                        await msg.finish(
                            f"{' '.join(file_info.get('gameVersions', []))} \
                                         \n{msg.session_info.locale.t('mod_dl.message.download_url')}{file_info.get('downloadUrl', '')} \
                                         \n{msg.session_info.locale.t('mod_dl.message.filename')}{file_info.get('fileName', '')}"
                        )
                else:
                    await msg.finish(I18NContext("mod_dl.message.version.not_found"))
