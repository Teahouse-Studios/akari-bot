import asyncio
import re

from core.builtins import Bot
from core.component import module
from core.config import Config
from core.utils.http import get_url
from core.utils.text import isint

mod_dl = module(
    bind_prefix='mod_dl',
    desc='{mod_dl.help.desc}', doc=True,
    developers=['HornCopper', 'OasisAkari', 'z0z0r4'],
    recommend_modules=['mcmod'],
    alias='moddl')

x_api_key = Config("curseforge_api_key", cfg_type=str, secret=True)
enable_mirror = bool(not x_api_key)  # CurseForge API Key 未配置，使用镜像 https://mcim.z0z0r4.top ...(z0z0r4 不想解析网页)


@mod_dl.command('<mod_name> [<version>] {{mod_dl.help}}')
async def _(msg: Bot.MessageSession, mod_name: str, version: str = None):
    ver = version
    if version:
        match_ver = re.match(r'^\d+\.\d+\.\d+$|^\d+\.\d+$|\d+w\d+[abcd]', version)
        if not match_ver:
            mod_name += ' ' + version
            ver = False

    async def search_modrinth(name: str, ver: str):
        url = f'https://api.modrinth.com/v2/search?query={name}&limit=10'
        if ver:
            url += f'&facets=[["versions:{ver}"],["project_type:mod"]]'
        else:
            url += '&facets=[["project_type:mod"]]'
        resp = await get_url(url, 200, fmt="json", timeout=5, attempt=3)
        if resp:
            results = []
            if len(resp["hits"]) == 0:
                return None
            for project in resp['hits']:
                results.append(("modrinth", project["title"], project["project_id"], project["versions"]))
            return results

    async def search_curseforge(name: str, ver: str):
        if enable_mirror:
            # https://mcim.z0z0r4.top/docs#/Curseforge/curseforge_search_curseforge_search_get
            url = f'https://mcim.z0z0r4.top/curseforge/search?gameId=432&searchFilter={
                name}&sortField=2&sortOrder=desc&pageSize=10&classId=6'
            headers = None
        else:
            headers = {
                'Accept': 'application/json',
                'x-api-key': x_api_key
            }
            url = f'https://api.curseforge.com/v1/mods/search?gameId=432&searchFilter={
                name}&sortField=2&sortOrder=desc&pageSize=10&classId=6'

        if ver:
            url += f'&gameVersion={ver}'
        results = []
        resp = await get_url(url, 200, fmt="json", timeout=5, attempt=3, headers=headers)
        if resp:
            if not enable_mirror:  # 没提供 pagination
                if resp["pagination"]["resultCount"] == 0:
                    return None
            for mod in resp["data"]:
                results.append(("curseforge", mod["name"], mod["id"], None))
        return results

    async def get_modrinth_project_version(project_id: str, ver: str):
        url = f'https://api.modrinth.com/v2/project/{project_id}/version?game_versions=["{ver}"]&featured=true'
        resp = (await get_url(url, 200, fmt="json", timeout=5, attempt=3))[0]
        if resp:
            return resp

    async def get_curseforge_mod_version_index(modid: str):
        if enable_mirror:
            # https://mcim.z0z0r4.top/docs#/Curseforge/get_mod_curseforge_mod__modid_slug__get
            url = f'https://mcim.z0z0r4.top/curseforge/mod/{modid}'
            headers = None
        else:
            headers = {
                'Accept': 'application/json',
                'x-api-key': x_api_key
            }
            url = f'https://api.curseforge.com/v1/mods/{modid}'
        resp = await get_url(url, 200, fmt="json", timeout=5, attempt=3, headers=headers)
        if resp:
            return resp["data"]['latestFilesIndexes']

    async def get_curseforge_mod_file(modid: str, ver: str):
        if enable_mirror:
            url = f'https://mcim.z0z0r4.top/curseforge/mod/{modid}/files?gameVersion={ver}'
            headers = None
        else:
            headers = {
                'Accept': 'application/json',
                'x-api-key': x_api_key
            }
            url = f'https://api.curseforge.com/v1/mods/{modid}/files?gameVersion={ver}'

        resp = await get_url(url, 200, fmt="json", timeout=5, attempt=3, headers=headers)
        if resp:
            return resp["data"][0]

    # 搜索 Mod
    result = await asyncio.gather(*(search_modrinth(mod_name, ver), search_curseforge(mod_name, ver)))
    cache_result = []
    if not result[0] and not result[1]:
        await msg.finish(msg.locale.t("mod_dl.message.not_found"))
    else:
        # 合并搜索结果
        reply_text, count = [], 0

        # 先显示 CurseForge 的结果
        if not result[1]:
            reply_text.append(msg.locale.t("mod_dl.message.curseforge.not_found"))
        else:
            reply_text.append(msg.locale.t("mod_dl.message.curseforge.result"))
            for mod in result[1]:
                count += 1
                reply_text.append(f"{count}. {mod[1]}")
                cache_result.append(mod)

        if not result[0]:
            reply_text.append(msg.locale.t("mod_dl.message.modrinth.not_found"))
        reply_text.append(msg.locale.t("mod_dl.message.modrinth.result"))
        for mod in result[0]:
            count += 1
            reply_text.append(f"{count}. {mod[1]}")
            cache_result.append(mod)

        reply = await msg.wait_reply('\n'.join(reply_text) + '\n' + msg.locale.t("mod_dl.message.prompt"), delete=True)
        replied = reply.as_display(text_only=True)

        # 查找 Mod
        if isint(replied):
            replied = int(replied)
            if not replied or replied > len(cache_result):
                await msg.finish(msg.locale.t("mod_dl.message.invalid.out_of_range"))
            else:
                mod_info = cache_result[replied - 1]
        else:
            await msg.finish(msg.locale.t("mod_dl.message.invalid.non_digital"))

        if mod_info[0] == "modrinth":  # modrinth mod
            if not ver:
                reply2 = await msg.wait_reply(f'{msg.locale.t("mod_dl.message.version")}\n'
                                              + "\n".join(mod_info[3])
                                              + f'\n{msg.locale.t("mod_dl.message.version.prompt")}', delete=True)
                replied2 = reply2.as_display(text_only=True)
                if replied2 in mod_info[3]:
                    version_info = await get_modrinth_project_version(mod_info[2], replied2)
                    if version_info:
                        await msg.finish(
                            f'{" ".join(version_info["loaders"])}\n{msg.locale.t("mod_dl.message.download_url")}{version_info["files"][0]["url"]}\n{msg.locale.t("mod_dl.message.filename")}{version_info["files"][0]["filename"]}')
                else:
                    await msg.finish()
            elif ver not in mod_info[3]:
                await msg.finish(msg.locale.t("mod_dl.message.version.not_found"))
            elif ver in mod_info[3]:
                version_info = await get_modrinth_project_version(mod_info[2], ver)
                if version_info:
                    await msg.finish(
                        f'{" ".join(version_info["loaders"])}\n{msg.locale.t("mod_dl.message.download_url")}{version_info["files"][0]["url"]}\n{msg.locale.t("mod_dl.message.filename")}{version_info["files"][0]["filename"]}')
        else:  # curseforge mod
            version_index, ver_list = await get_curseforge_mod_version_index(mod_info[2]), []
            for version_ in version_index:
                if version_["gameVersion"] not in ver_list:
                    ver_list.append(version_["gameVersion"])
            if version_index:
                if not ver:
                    reply2 = await msg.wait_reply(f'{msg.locale.t("mod_dl.message.version")}\n' +
                                                  '\n'.join(ver_list) +
                                                  f'\n{msg.locale.t("mod_dl.message.version.prompt")}', delete=True)
                    ver = reply2.as_display(text_only=True)
                elif ver not in ver_list:
                    await msg.finish(msg.locale.t("mod_dl.message.version.not_found"))

                if ver in ver_list:
                    file_info = await get_curseforge_mod_file(mod_info[2], ver)
                    if file_info:
                        await msg.finish(f'{" ".join(file_info["gameVersions"])} \
                                         \n{msg.locale.t("mod_dl.message.download_url")}{file_info["downloadUrl"]} \
                                         \n{msg.locale.t("mod_dl.message.filename")}{file_info["fileName"]}')
                else:
                    await msg.finish(msg.locale.t("mod_dl.message.version.not_found"))
