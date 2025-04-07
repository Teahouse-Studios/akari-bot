import os
import sys

import ast
import orjson as json

from tortoise.models import Model
from tortoise import fields, run_async, Tortoise

if __name__ == "__main__":
    sys.path.append(os.getcwd())

from core.constants.version import database_version
from core.database_v2 import fetch_module_db
from core.database_v2.link import get_db_link
from core.logger import Logger

from core.database_v2.models import *
from modules.cytoid.database.models import *
from modules.maimai.database.models import *
from modules.osu.database.models import *
from modules.phigros.database.models import *
from modules.wiki.database.models import *
from modules.wikilog.database.models import *


class SenderInfoL(Model):
    id = fields.CharField(max_length=512, pk=True)
    isInBlockList = fields.BooleanField(default=False)
    isInAllowList = fields.BooleanField(default=False)
    isSuperUser = fields.BooleanField(default=False)
    warns = fields.IntField(default=0)
    disableTyping = fields.BooleanField(default=False)
    petal = fields.IntField(default=0)

    class Meta:
        table = "SenderInfo"


class TargetInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    enabledModules = fields.JSONField(default=[])
    options = fields.JSONField(default={})
    customAdmins = fields.JSONField(default=[])
    muted = fields.BooleanField(default=False)
    locale = fields.CharField(max_length=512)

    class Meta:
        table = "TargetInfo"


class GroupBlockList(Model):
    targetId = fields.CharField(max_length=512, pk=True)

    class Meta:
        table = "GroupBlockList"


class StoredDataL(Model):
    name = fields.CharField(max_length=512, pk=True)
    value = fields.CharField(max_length=512)

    class Meta:
        table = "StoredData"


class Analytics(Model):
    id = fields.IntField(pk=True)
    moduleName = fields.CharField(max_length=512)
    moduleType = fields.CharField(max_length=512)
    targetId = fields.CharField(max_length=512)
    senderId = fields.CharField(max_length=512)
    command = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField()

    class Meta:
        table = "Analytics"


class UnfriendlyActionsTable(Model):
    id = fields.CharField(max_length=512, pk=True)
    targetId = fields.CharField(max_length=512)
    senderId = fields.CharField(max_length=512)
    action = fields.CharField(max_length=512)
    detail = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField()

    class Meta:
        table = "unfriendly_action"


class CytoidBindInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "module_cytoid_CytoidBindInfo"


class DivingProberBindInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "module_maimai_DivingProberBindInfo"


class OsuBindInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "module_osu_OsuBindInfo"


class PhigrosBindInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    sessiontoken = fields.CharField(max_length=512)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "module_phigros_PgrBindInfo"


class WikiTargetInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    link = fields.CharField(max_length=512, null=True)
    iws = fields.JSONField(default={})
    headers = fields.JSONField(default={"accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"})
    prefix = fields.CharField(max_length=512, null=True)

    class Meta:
        table = "module_wiki_TargetSetInfo"


class WikiSiteInfoL(Model):
    apiLink = fields.CharField(max_length=512, pk=True)
    siteInfo = fields.JSONField(default={})
    timestamp = fields.DatetimeField()

    class Meta:
        table = "module_wiki_WikiInfo"


class WikiAllowListL(Model):
    apiLink = fields.CharField(max_length=512, pk=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "module_wiki_WikiAllowList"


class WikiBlockListL(Model):
    apiLink = fields.CharField(max_length=512, pk=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "module_wiki_WikiBlockList"


class WikiBotAccountListL(Model):
    apiLink = fields.CharField(max_length=512, pk=True)
    botAccount = fields.CharField(max_length=512)
    botPassword = fields.CharField(max_length=512)

    class Meta:
        table = "module_wiki_WikiBotAccountList"


class WikiLogTargetSetInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    infos = fields.TextField()

    class Meta:
        table = "module_wikilog_WikiLogTargetSetInfo"


async def convert_database():
    database_list = fetch_module_db()

    await Tortoise.init(
        db_url=get_db_link("tortoise"),
        modules={'models': ['__main__', "core.database_v2.models"] + database_list}
    )
    await Tortoise.generate_schemas()

    conn = Tortoise.get_connection("default")

    sender_info_records = await SenderInfoL.all()
    for r in sender_info_records:
        try:
            await SenderInfo.create(
                sender_id=r.id,
                blocked=r.isInBlockList,
                trusted=r.isInAllowList,
                superuser=r.isSuperUser,
                warns=r.warns,
                petal=r.petal,
                sender_data={"disable_typing": r.disableTyping}
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS SenderInfo;")

    target_info_records = await TargetInfoL.all()
    group_block_records = await GroupBlockList.all()
    blocked_target_ids = {record.targetId for record in group_block_records}

    for r in target_info_records:
        try:
            await TargetInfo.create(
                target_id=r.targetId,
                blocked=False,
                muted=r.muted,
                locale=r.locale,
                modules=r.enabledModules,
                custom_admins=r.customAdmins,
                target_data=r.options
            )
        except Exception:
            continue

        if r.targetId in blocked_target_ids:
            target_info_record = await TargetInfo.get_or_none(target_id=r.targetId)
            if target_info_record:
                target_info_record.blocked = True
                await target_info_record.save()
            else:
                await TargetInfo.create(
                    target_id=r.targetId,
                    blocked=True
                )
    await conn.execute_script("DROP TABLE IF EXISTS TargetInfo;")
    await conn.execute_script("DROP TABLE IF EXISTS GroupBlockList;")

    stored_data_records = await StoredDataL.all()
    for r in stored_data_records:
        v = r.value.strip()
        try:
            v = ast.literal_eval(v)
        except (SyntaxError, ValueError):
            continue

        try:
            await StoredData.create(
                stored_key=r.name,
                value=v
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS StoredData;")

    analytics_records = await Analytics.all()
    for r in analytics_records:
        try:
            await AnalyticsData.create(
                id=r.id,
                module_name=r.moduleName,
                module_type=r.moduleType,
                target_id=r.targetId,
                sender_id=r.senderId,
                command=r.command,
                timestamp=r.timestamp
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS Analytics;")

    unfriendly_action_record = await UnfriendlyActionsTable.all()
    for r in unfriendly_action_record:
        try:
            await UnfriendlyActionRecords.create(
                id=r.id,
                target_id=r.targetId,
                sender_id=r.senderId,
                timestamp=r.timestamp,
                action=r.action,
                detail=r.detail,
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS unfriendly_action;")

    cytoid_bind_record = await CytoidBindInfoL.all()
    for r in cytoid_bind_record:
        try:
            await CytoidBindInfo.create(
                sender_id=r.targetId,
                username=r.username,
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_cytoid_CytoidBindInfo;")

    maimai_bind_record = await DivingProberBindInfoL.all()
    for r in maimai_bind_record:
        try:
            await DivingProberBindInfo.create(
                sender_id=r.targetId,
                username=r.username,
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_maimai_DivingProberBindInfo;")

    osu_bind_record = await OsuBindInfoL.all()
    for r in osu_bind_record:
        try:
            await OsuBindInfo.create(
                sender_id=r.targetId,
                username=r.username,
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_osu_OsuBindInfo;")

    phigros_bind_record = await PhigrosBindInfoL.all()
    for r in phigros_bind_record:
        try:
            await PhigrosBindInfo.create(
                sender_id=r.targetId,
                session_token=r.sessiontoken,
                username=r.username,
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_phigros_PgrBindInfo;")

    wiki_target_info_record = await WikiTargetInfoL.all()
    for r in wiki_target_info_record:
        try:
            await WikiTargetInfo.create(
                target_id=r.targetId,
                api_link=r.link,
                interwikis=r.iws,
                headers=r.headers,
                prefix=r.prefix,
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_wiki_TargetSetInfo;")

    wiki_site_info_record = await WikiSiteInfoL.all()
    for r in wiki_site_info_record:
        try:
            await WikiSiteInfo.create(
                api_link=r.apiLink,
                site_info=r.siteInfo,
                timestamp=r.timestamp
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_wiki_WikiInfo;")

    wiki_allow_list_record = await WikiAllowListL.all()
    for r in wiki_allow_list_record:
        try:
            await WikiAllowList.create(
                api_link=r.apiLink,
                timestamp=r.timestamp
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_wiki_WikiAllowList;")

    wiki_block_list_record = await WikiBlockListL.all()
    for r in wiki_block_list_record:
        try:
            await WikiBlockList.create(
                api_link=r.apiLink,
                timestamp=r.timestamp
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_wiki_WikiBlockList;")

    wiki_account_list_record = await WikiBotAccountListL.all()
    for r in wiki_account_list_record:
        try:
            await WikiBotAccountList.create(
                api_link=r.apiLink,
                bot_account=r.botAccount,
                bot_password=r.botPassword
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_wiki_WikiBotAccountList;")

    wikilog_target_set_info_record = await WikiLogTargetSetInfoL.all()
    for r in wikilog_target_set_info_record:
        try:
            await WikiLogTargetSetInfo.create(
                target_id=r.targetId,
                infos=json.loads(r.infos)
            )
        except Exception:
            continue
    await conn.execute_script("DROP TABLE IF EXISTS module_wikilog_WikiLogTargetSetInfo;")

    await conn.execute_script("DROP TABLE IF EXISTS job_queues;")
    await conn.execute_script("DROP TABLE IF EXISTS DBVersion;")

    db_v = await DBVersion.first()
    if db_v:
        await db_v.delete()
    await DBVersion.create(version=database_version)

    await Tortoise.close_connections()

if __name__ == "__main__":
    run_async(convert_database())
    Logger.info("Database converted successfully!")
