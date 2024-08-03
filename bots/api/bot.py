import os
import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
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
jwt_secret = Config('jwt_secret', cfg_type=str)


@app.on_event("startup")
async def startup_event():
    await init_async(start_scheduler=False)
    load_extra_schedulers()
    Scheduler.start()
    await JobQueue.secret_append_ip()


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
            "detail": "Not Found"
        })
    enabled_modules = target.enabled_modules
    is_muted = target.is_muted
    custom_admins = target.custom_admins
    locale = target.locale
    petal = target.petal

    command_alias = target.get_option('command_alias', {})
    command_prefix = target.get_option('command_prefix', [])
    ban = target.get_option('ban', [])
    typo_check = target.get_option('typo_check', False)
    cooldown_time = target.get_option('cooldown_time', 0)
    in_post_whitelist = target.get_option('in_post_whitelist', False)

    dice_dc_reversed = target.get_option('dice_dc_reversed', False)
    dice_default_sides = target.get_option('dice_default_sides', 0)

    wiki_target = WikiTargetInfo(target_id)
    wiki_headers = wiki_target.get_headers()
    wiki_start_wiki = wiki_target.get_start_wiki()
    wiki_interwikis = wiki_target.get_interwikis()
    wiki_redlink = target.get_option('wiki_redlink', False)

    wordle_dark_theme = target.get_option('wordle_dark_theme', False)

    return {
        'targetId': target_id,
        'enabledModules': enabled_modules,
        'isMuted': is_muted,
        'customAdmins': custom_admins,
        'locale': locale,
        'petal': petal,
        'commandAlias': command_alias,
        'commandPrefix': command_prefix,
        'ban': ban,
        'typoCheck': typo_check,
        'cooldownTime': cooldown_time,
        'inPostWhitelist': in_post_whitelist,
        'dice': {
            'DCReversed': dice_dc_reversed,
            'defaultFace': dice_default_sides,
        },
        'wiki': {
            'headers': wiki_headers,
            'startWiki': wiki_start_wiki,
            'interwikis': wiki_interwikis,
            'redlink': wiki_redlink
        },
        'wordle': {
            'darkTheme': wordle_dark_theme,
        }
    }


@app.get('/sender/{sender_id}')
async def get_sender(sender_id: str):
    sender = BotDBUtil.SenderInfo(sender_id)
    if not sender.query:
        return JSONResponse(status_code=404, content={
            "detail": "Not Found"
        })

    return {
        'senderId': sender_id,
        'isInBlockList': sender.is_in_block_list,
        'isInAllowList': sender.is_in_allow_list,
        'isSuperUser': sender.is_super_user,
        'warns': sender.warns,
        'disableTyping': sender.disable_typing
    }


@app.get('/modules')
async def get_module_list():
    return {'modules': ModulesManager.return_modules_list()}


@app.get('/modules/{target_id}')
async def get_target_modules(target_id: str):
    target_data = BotDBUtil.TargetInfo(target_id)
    if not target_data.query:
        return JSONResponse(status_code=404, content={
            "detail": "Not Found"
        })
    target_from = '|'.join(target_id.split('|')[:-2])
    modules = ModulesManager.return_modules_list(
        target_from=target_from)
    enabled_modules = target_data.enabled_modules
    return {
        'targetId': target_id,
        'modules': {k: v for k, v in modules.items() if k in enabled_modules}
    }


@app.post('/modules/{target_id}/enable')
async def enable_modules(target_id: str, request: Request):
    try:
        target_data = BotDBUtil.TargetInfo(target_id)
        if not target_data.query:
            return JSONResponse(status_code=404, content={
                "detail": "Not Found"
            })
        target_from = '|'.join(target_id.split('|')[:-2])

        body = await request.json()
        modules = body["modules"]
        modules = modules if isinstance(modules, list) else [modules]
        modules = [m for m in modules if m in ModulesManager.return_modules_list(target_from=target_from)]
        target_data.enable(modules)
        return {"message": "success"}
    except Exception:
        raise JSONResponse(status_code=400, content={
            "detail": "Bad Request",
            "message": "error"
        })


@app.post('/modules/{target_id}/disable')
async def enable_modules(target_id: str, request: Request):
    try:
        target_data = BotDBUtil.TargetInfo(target_id)
        if not target_data.query:
            return JSONResponse(status_code=404, content={
                "detail": "Not Found"
            })
        target_from = '|'.join(target_id.split('|')[:-2])

        body = await request.json()
        modules = body["modules"]
        modules = modules if isinstance(modules, list) else [modules]
        modules = [m for m in modules if m in ModulesManager.return_modules_list(target_from=target_from)]
        target_data.disable(modules)
        return {"message": "success"}
    except Exception as e:
        Logger.error(str(e))
        return JSONResponse(status_code=400, content={
            "detail": "Bad Request",
            "message": "error"
        })


@app.get('/locale/{locale}/{string}')
async def get_locale(locale: str, string: str):
    try:
        return {
            'locale': locale,
            'string': string,
            'translation': Locale(locale).t(string, False),
        }
    except TypeError:
        return JSONResponse(status_code=404, content={
            "detail": "Not Found"
        })

if __name__ == "__main__":
    while True:
        uvicorn.run("bot:app", port=Config('api_port', 5000), log_level="info")
        Logger.error('API Server crashed, is the port occupied?')
        Logger.error('Retrying in 5 seconds...')
        time.sleep(5)
