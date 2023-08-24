import datetime
import os
import sys
from fastapi.responses import JSONResponse
import uvicorn
from fastapi import FastAPI
import jwt

sys.path.append(os.getcwd())

from config import Config  # noqa: E402
from database import BotDBUtil  # noqa: E402
from modules.wiki.utils.dbutils import WikiTargetInfo  # noqa: E402

app = FastAPI()
jwt_secret = Config('jwt_secret')


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
    if target.query is None:
        return JSONResponse(status_code=404, content={
            'targetId': target_id,
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
    wiki_fandom_addon = target.get_option('wiki_fandom_addon')

    wiki_target = WikiTargetInfo(target_id)
    wiki_headers = wiki_target.get_headers()
    wiki_start_wiki = wiki_target.get_start_wiki()
    wiki_interwikis = wiki_target.get_interwikis()

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
        'diceDcReversed': dice_dc_reversed,
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
    isInBlockList = sender.query.isInBlockList
    isInAllowList = sender.query.isInAllowList
    isSuperUser = sender.query.isSuperUser
    warns = sender.query.warns
    disable_typing = sender.query.disable_typing

    return {
        'senderId': sender_id,
        'isInBlockList': isInBlockList,
        'isInAllowList': isInAllowList,
        'isSuperUser': isSuperUser,
        'warns': warns,
        'disableTyping': disable_typing
    }


if __name__ == "__main__":
    uvicorn.run("bot:app", port=Config('api_port') or 5000, log_level="info", reload=True)
