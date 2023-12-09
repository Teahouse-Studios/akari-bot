import asyncio
import os
import sys
from datetime import datetime

import ujson as json

from core.builtins import Bot, PrivateAssets, ExecutionLockList, MessageTaskManager
from core.component import module
from core.logger import Logger
from core.utils.info import Info

upd = module('update', required_superuser=True, base=True)


def pull_repo():
    return os.popen('git pull', 'r').read()[:-1]


def update_dependencies():
    poetry_install = os.popen('poetry install').read()[:-1]
    if poetry_install != '':
        return poetry_install
    pip_install = os.popen('pip install -r requirements.txt').read()[:-1]
    if len(pip_install) > 500:
        return '...' + pip_install[-500:]
    return


@upd.command()
async def update_bot(msg: Bot.MessageSession):
    confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False)
    if confirm:
        pull_repo_result = pull_repo()
        if pull_repo_result != '':
            await msg.send_message(pull_repo_result)
        else:
            await msg.send_message(msg.locale.t("core.message.update.failed"))
        await msg.send_message(update_dependencies())

if Info.subprocess:
    rst = module('restart', required_superuser=True, base=True)

    def restart():
        sys.exit(233)

    def write_version_cache(msg: Bot.MessageSession):
        update = os.path.abspath(PrivateAssets.path + '/cache_restart_author')
        write_version = open(update, 'w')
        write_version.write(json.dumps({'From': msg.target.target_from, 'ID': msg.target.target_id}))
        write_version.close()

    restart_time = []

    async def wait_for_restart(msg: Bot.MessageSession):
        get = ExecutionLockList.get()
        if datetime.now().timestamp() - restart_time[0] < 60:
            if len(get) != 0:
                await msg.send_message(msg.locale.t("core.message.restart.wait", count=len(get)))
                await asyncio.sleep(10)
                return await wait_for_restart(msg)
            else:
                await msg.send_message(msg.locale.t("core.message.restart.restarting"))
                get_wait_list = MessageTaskManager.get()
                for x in get_wait_list:
                    for y in get_wait_list[x]:
                        for z in get_wait_list[x][y]:
                            if get_wait_list[x][y][z]['active']:
                                await z.send_message(z.locale.t("core.message.restart.prompt"))

        else:
            await msg.send_message(msg.locale.t("core.message.restart.timeout"))

    @rst.command()
    async def restart_bot(msg: Bot.MessageSession):
        confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False)
        if confirm:
            restart_time.append(datetime.now().timestamp())
            await wait_for_restart(msg)
            write_version_cache(msg)
            restart()


if Info.subprocess:
    upds = module('update&restart', required_superuser=True, alias='u&r', base=True)

    @upds.command()
    async def update_and_restart_bot(msg: Bot.MessageSession):
        confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False)
        if confirm:
            restart_time.append(datetime.now().timestamp())
            await wait_for_restart(msg)
            write_version_cache(msg)
            pull_repo_result = pull_repo()
            if pull_repo_result != '':
                await msg.send_message(pull_repo_result)
                await msg.send_message(update_dependencies())
            else:
                Logger.warn(f'Failed to get Git repository result.')
                await msg.send_message(msg.locale.t("core.message.update.failed"))
            restart()
