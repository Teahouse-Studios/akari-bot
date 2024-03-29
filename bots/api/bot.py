
import os
import sys
import time

from fastapi.responses import JSONResponse
import uvicorn
from fastapi import FastAPI
import jwt

from core.queue import JobQueue
from core.scheduler import Scheduler

sys.path.append(os.getcwd())

from core.loader import ModulesManager  # noqa: E402
from core.utils.i18n import Locale  # noqa: E402
from core.utils.bot import init_async, load_prompt  # noqa: E402
from core.extra.scheduler import load_extra_schedulers  # noqa: E402
from config import Config  # noqa: E402
from database import BotDBUtil  # noqa: E402
from modules.wiki.utils.dbutils import WikiTargetInfo  # noqa: E402
from core.logger import Logger  # noqa: E402


app = FastAPI()
jwt_secret = Config('jwt_secret')


@app.on_event("startup")
async def startup_event():
    await init_async(start_scheduler=False)
    load_extra_schedulers()
    Scheduler.start()
    await JobQueue.secret_append_ip()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get('/auth/{token}')
async def auth(token: str):
    try:
        return jwt.decode(token, jwt_secret, algorithms=['HS256'])
    except jwt.InvalidSignatureError:
        return JSONResponse(status_code=403, content={
            'token': token,
            'invalid': True
        })


@app.get('/target/{target_id}')
async def get_target(target_id: str):
    target = BotDBUtil.TargetInfo(target_id)
    if not target.query:
        return JSONResponse(status_code=404, content={
            'target_id': target_id,
            'notFound': True,
        })
    enabled_modules = target.enabled_modules
    is_muted = target.is_muted
    custom_admins = target.custom_admins
    locale = target.locale
    petal = target.petal

    command_alias = target.get_option('command_alias')
    command_prefix = target.get_option('command_prefix')
    ban = target.get_option('ban')
    typo_check = target.get_option('typo_check')
    dice_dc_reversed = target.get_option('dice_dc_reversed')
    dice_default_sides = target.get_option('dice_default_sides')
    wiki_fandom_addon = target.get_option('wiki_fandom_addon')
    wordle_dark_theme = target.get_option('wordle_dark_theme')

    wiki_target = WikiTargetInfo(target_id)
    wiki_headers = wiki_target.get_headers()
    wiki_start_wiki = wiki_target.get_start_wiki()
    wiki_interwikis = wiki_target.get_interwikis()

    return {
        'target_id': target_id,
        'enabledModules': enabled_modules,
        'isMuted': is_muted,
        'customAdmins': custom_admins,
        'locale': locale,
        'petal': petal,
        'commandAlias': command_alias,
        'commandPrefix': command_prefix,
        'ban': ban,
        'typoCheck': typo_check,
        'diceDCReversed': dice_dc_reversed,
        'diceDefaultFace': dice_default_sides,
        'wordleDarkTheme': wordle_dark_theme,
        'wiki': {
            'fandomAddon': wiki_fandom_addon,
            'headers': wiki_headers,
            'startWiki': wiki_start_wiki,
            'interwikis': wiki_interwikis
        }
    }


@app.get('/sender/{sender_id}')
async def get_sender(sender_id: str):
    sender = BotDBUtil.SenderInfo(sender_id)

    return {
        'senderId': sender_id,
        'isInBlockList': sender.query.isInBlockList,
        'isInAllowList': sender.query.isInAllowList,
        'isSuperUser': sender.query.isSuperUser,
        'warns': sender.query.warns,
        'disableTyping': sender.query.disable_typing
    }


@app.get('/module/{target_id}')
async def get_module_list(target_id: str):
    target_from = '|'.join(target_id.split('|')[:-2])
    return ModulesManager.return_modules_list(
        target_from=target_from)


@app.post('/module/{target_id}/{module_name}')
async def set_module(target_id: str, module_name: str, enable: bool):
    target_from = '|'.join(target_id.split('|')[:-2])
    return ModulesManager.set_module(
        targetFrom=target_from,
        moduleName=module_name,
        enable=enable)


@app.get('/locale/{locale}/{string}')
async def get_translation(locale: str, string: str):
    try:
        return {
            'locale': locale,
            'string': string,
            'translation': Locale(locale).t(string, False),
        }
    except TypeError:
        return JSONResponse(status_code=404, content={
            'locale': locale,
            'string': string,
            'notFound': True,
        })

if __name__ == "__main__":
    while True:
        uvicorn.run("bot:app", port=Config('api_port', 5000), log_level="info")
        Logger.error('API Server crashed, is the port occupied?')
        Logger.error('Retrying in 5 seconds...')
        time.sleep(5)
