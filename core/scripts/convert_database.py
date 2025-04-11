import os
import sys

import orjson as json

from tortoise.models import Model
from tortoise import fields, run_async, Tortoise

if __name__ == "__main__":
    sys.path.append(os.getcwd())

from core.constants.version import database_version
from core.database import fetch_module_db
from core.database.link import get_db_link
from core.database.models import *
from core.logger import Logger
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
        table = "_old_SenderInfo"


class TargetInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    enabledModules = fields.JSONField(default=[])
    options = fields.JSONField(default={})
    customAdmins = fields.JSONField(default=[])
    muted = fields.BooleanField(default=False)
    locale = fields.CharField(max_length=512)

    class Meta:
        table = "_old_TargetInfo"


class GroupBlockList(Model):
    targetId = fields.CharField(max_length=512, pk=True)

    class Meta:
        table = "_old_GroupBlockList"


class StoredDataL(Model):
    name = fields.CharField(max_length=512, pk=True)
    value = fields.CharField(max_length=512)

    class Meta:
        table = "_old_StoredData"


class Analytics(Model):
    id = fields.IntField(pk=True)
    moduleName = fields.CharField(max_length=512)
    moduleType = fields.CharField(max_length=512)
    targetId = fields.CharField(max_length=512)
    senderId = fields.CharField(max_length=512)
    command = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField()

    class Meta:
        table = "_old_Analytics"


class UnfriendlyActionsTable(Model):
    id = fields.CharField(max_length=512, pk=True)
    targetId = fields.CharField(max_length=512)
    senderId = fields.CharField(max_length=512)
    action = fields.CharField(max_length=512)
    detail = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField()

    class Meta:
        table = "_old_unfriendly_action"


class CytoidBindInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "_old_module_cytoid_CytoidBindInfo"


class DivingProberBindInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "_old_module_maimai_DivingProberBindInfo"


class OsuBindInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "_old_module_osu_OsuBindInfo"


class PhigrosBindInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    sessiontoken = fields.CharField(max_length=512)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "_old_module_phigros_PgrBindInfo"


class WikiTargetInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    link = fields.CharField(max_length=512, null=True)
    iws = fields.JSONField(default={})
    headers = fields.JSONField(default={"accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"})
    prefix = fields.CharField(max_length=512, null=True)

    class Meta:
        table = "_old_module_wiki_TargetSetInfo"


class WikiSiteInfoL(Model):
    apiLink = fields.CharField(max_length=512, pk=True)
    siteInfo = fields.JSONField(default={})
    timestamp = fields.DatetimeField()

    class Meta:
        table = "_old_module_wiki_WikiInfo"


class WikiAllowListL(Model):
    apiLink = fields.CharField(max_length=512, pk=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "_old_module_wiki_WikiAllowList"


class WikiBlockListL(Model):
    apiLink = fields.CharField(max_length=512, pk=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "_old_module_wiki_WikiBlockList"


class WikiBotAccountListL(Model):
    apiLink = fields.CharField(max_length=512, pk=True)
    botAccount = fields.CharField(max_length=512)
    botPassword = fields.CharField(max_length=512)

    class Meta:
        table = "_old_module_wiki_WikiBotAccountList"


class WikiLogTargetSetInfoL(Model):
    targetId = fields.CharField(max_length=512, pk=True)
    infos = fields.TextField()

    class Meta:
        table = "_old_module_wikilog_WikiLogTargetSetInfo"


database_list = fetch_module_db()


async def rename_old_tables():
    Logger.warning("Renaming old tables...")
    await Tortoise.init(
        db_url=get_db_link(),
        modules={"models": ["core.scripts.convert_database"]}
    )
    conn = Tortoise.get_connection("default")

    # Renaming old tables to avoid conflicts
    # Start with "_old" to order them at the end of the list
    try:
        await conn.execute_script("ALTER TABLE SenderInfo RENAME TO _old_SenderInfo;")
        await conn.execute_script("ALTER TABLE TargetInfo RENAME TO _old_TargetInfo;")
        await conn.execute_script("ALTER TABLE GroupBlockList RENAME TO _old_GroupBlockList;")
        await conn.execute_script("ALTER TABLE StoredData RENAME TO _old_StoredData;")
        await conn.execute_script("ALTER TABLE Analytics RENAME TO _old_Analytics;")
        await conn.execute_script("ALTER TABLE unfriendly_action RENAME TO _old_unfriendly_action;")
        await conn.execute_script("ALTER TABLE module_cytoid_CytoidBindInfo RENAME TO _old_module_cytoid_CytoidBindInfo;")
        await conn.execute_script("ALTER TABLE module_maimai_DivingProberBindInfo RENAME TO _old_module_maimai_DivingProberBindInfo;")
        await conn.execute_script("ALTER TABLE module_osu_OsuBindInfo RENAME TO _old_module_osu_OsuBindInfo;")
        await conn.execute_script("ALTER TABLE module_phigros_PgrBindInfo RENAME TO _old_module_phigros_PgrBindInfo;")
        await conn.execute_script("ALTER TABLE module_wiki_TargetSetInfo RENAME TO _old_module_wiki_TargetSetInfo;")
        await conn.execute_script("ALTER TABLE module_wiki_WikiInfo RENAME TO _old_module_wiki_WikiInfo;")
        await conn.execute_script("ALTER TABLE module_wiki_WikiAllowList RENAME TO _old_module_wiki_WikiAllowList;")
        await conn.execute_script("ALTER TABLE module_wiki_WikiBlockList RENAME TO _old_module_wiki_WikiBlockList;")
        await conn.execute_script("ALTER TABLE module_wiki_WikiBotAccountList RENAME TO _old_module_wiki_WikiBotAccountList;")
        await conn.execute_script("ALTER TABLE module_wikilog_WikiLogTargetSetInfo RENAME TO _old_module_wikilog_WikiLogTargetSetInfo;")
        await conn.execute_script("ALTER TABLE job_queues RENAME TO _old_job_queues;")
        await conn.execute_script("ALTER TABLE DBVersion RENAME TO _old_DBVersion;")
    except Exception:
        pass

    await Tortoise.close_connections()


async def convert_database():
    Logger.warning("Start converting old database...")

    await rename_old_tables()

    await Tortoise.init(
        db_url=get_db_link(),
        modules={"models": ["core.scripts.convert_database", "core.database.models"] + database_list}
    )

    await Tortoise.generate_schemas(safe=True)

    Logger.warning("Converting old database data...")

    Logger.info("Converting SenderInfo...")
    sender_info_records = await SenderInfoL.all()
    i = 0
    for r in sender_info_records:
        i += 1
        if i % 1000 == 0:
            Logger.info(f"Converting SenderInfo {i}/{len(sender_info_records)}...")
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
        except Exception as e:
            Logger.error(f"Failed to convert SenderInfo: {r.id}, error: {e}")
            Logger.error(f"SenderInfo record: {r.__dict__}")

    Logger.info("Converting TargetInfo...")

    target_info_records = await TargetInfoL.all()
    group_block_records = await GroupBlockList.all()
    blocked_target_ids = {record.targetId for record in group_block_records}
    i = 0
    for r in target_info_records:
        i += 1
        if i % 1000 == 0:
            Logger.info(f"Converting TargetInfo {i}/{len(target_info_records)}...")
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
        except Exception as e:
            Logger.error(f"Failed to convert TargetInfo: {r.targetId}, error: {e}")
            Logger.error(f"TargetInfo record: {r.__dict__}")

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

    Logger.info("Converting StoredData...")

    stored_data_records = await StoredDataL.all()
    for r in stored_data_records:
        v = r.value.strip()
        if not (v.startswith("[") and v.endswith("]")):
            v = f"[{v}]"
        try:
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                continue

            await StoredData.create(
                stored_key=r.name,
                value=v
            )
        except Exception as e:
            Logger.error(f"Failed to convert StoredData: {r.name}, error: {e}")
            Logger.error(f"StoredData record: {r.__dict__}")

    Logger.info("Converting Analytics...")

    analytics_records = await Analytics.all()
    i = 0
    for r in analytics_records:
        i += 1
        if i % 1000 == 0:
            Logger.info(f"Converting Analytics {i}/{len(analytics_records)}...")
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
        except Exception as e:
            Logger.error(f"Failed to convert Analytics: {r.id}, error: {e}")
            Logger.error(f"Analytics record: {r.__dict__}")

    Logger.info("Converting UnfriendlyActions...")

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
        except Exception as e:
            Logger.error(f"Failed to convert UnfriendlyActionRecords: {r.id}, error: {e}")
            Logger.error(f"UnfriendlyActionRecords record: {r.__dict__}")

    Logger.info("Converting CytoidBindInfo...")

    cytoid_bind_record = await CytoidBindInfoL.all()
    for r in cytoid_bind_record:
        try:
            await CytoidBindInfo.create(
                sender_id=r.targetId,
                username=r.username,
            )
        except Exception as e:
            Logger.error(f"Failed to convert CytoidBindInfo: {r.targetId}, error: {e}")
            Logger.error(f"CytoidBindInfo record: {r.__dict__}")

    Logger.info("Converting DivingProberBindInfo...")

    maimai_bind_record = await DivingProberBindInfoL.all()
    for r in maimai_bind_record:
        try:
            await DivingProberBindInfo.create(
                sender_id=r.targetId,
                username=r.username,
            )
        except Exception as e:
            Logger.error(f"Failed to convert DivingProberBindInfo: {r.targetId}, error: {e}")
            Logger.error(f"DivingProberBindInfo record: {r.__dict__}")

    Logger.info("Converting OsuBindInfo...")

    osu_bind_record = await OsuBindInfoL.all()
    for r in osu_bind_record:
        try:
            await OsuBindInfo.create(
                sender_id=r.targetId,
                username=r.username,
            )
        except Exception as e:
            Logger.error(f"Failed to convert OsuBindInfo: {r.targetId}, error: {e}")
            Logger.error(f"OsuBindInfo record: {r.__dict__}")

    Logger.info("Converting PhigrosBindInfo...")

    phigros_bind_record = await PhigrosBindInfoL.all()
    for r in phigros_bind_record:
        try:
            await PhigrosBindInfo.create(
                sender_id=r.targetId,
                session_token=r.sessiontoken,
                username=r.username,
            )
        except Exception as e:
            Logger.error(f"Failed to convert PhigrosBindInfo: {r.targetId}, error: {e}")
            Logger.error(f"PhigrosBindInfo record: {r.__dict__}")

    Logger.info("Converting WikiTargetInfo...")

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
        except Exception as e:
            Logger.error(f"Failed to convert WikiTargetInfo: {r.targetId}, error: {e}")
            Logger.error(f"WikiTargetInfo record: {r.__dict__}")

    Logger.info("Converting WikiSiteInfo...")

    wiki_site_info_record = await WikiSiteInfoL.all()
    for r in wiki_site_info_record:
        try:
            await WikiSiteInfo.create(
                api_link=r.apiLink,
                site_info=r.siteInfo,
                timestamp=r.timestamp
            )
        except Exception as e:
            Logger.error(f"Failed to convert WikiSiteInfo: {r.apiLink}, error: {e}")
            Logger.error(f"WikiSiteInfo record: {r.__dict__}")

    Logger.info("Converting WikiAllowList...")

    wiki_allow_list_record = await WikiAllowListL.all()
    for r in wiki_allow_list_record:
        try:
            await WikiAllowList.create(
                api_link=r.apiLink,
                timestamp=r.timestamp
            )
        except Exception as e:
            Logger.error(f"Failed to convert WikiAllowList: {r.apiLink}, error: {e}")
            Logger.error(f"WikiAllowList record: {r.__dict__}")

    Logger.info("Converting WikiBlockList...")

    wiki_block_list_record = await WikiBlockListL.all()
    for r in wiki_block_list_record:
        try:
            await WikiBlockList.create(
                api_link=r.apiLink,
                timestamp=r.timestamp
            )
        except Exception as e:
            Logger.error(f"Failed to convert WikiBlockList: {r.apiLink}, error: {e}")
            Logger.error(f"WikiBlockList record: {r.__dict__}")

    Logger.info("Converting WikiBotAccountList...")

    wiki_account_list_record = await WikiBotAccountListL.all()
    for r in wiki_account_list_record:
        try:
            await WikiBotAccountList.create(
                api_link=r.apiLink,
                bot_account=r.botAccount,
                bot_password=r.botPassword
            )
        except Exception as e:
            Logger.error(f"Failed to convert WikiBotAccountList: {r.apiLink}, error: {e}")
            Logger.error(f"WikiBotAccountList record: {r.__dict__}")

    Logger.info("Converting WikiLogTargetSetInfo...")

    wikilog_target_set_info_record = await WikiLogTargetSetInfoL.all()
    for r in wikilog_target_set_info_record:
        try:
            await WikiLogTargetSetInfo.create(
                target_id=r.targetId,
                infos=json.loads(r.infos)
            )
        except Exception as e:
            Logger.error(f"Failed to convert WikiLogTargetSetInfo: {r.targetId}, error: {e}")
            Logger.error(f"WikiLogTargetSetInfo record: {r.__dict__}")

    Logger.info("Converting DBVersion...")

    db_v = await DBVersion.first()
    if db_v:
        await db_v.delete()
    await DBVersion.create(version=database_version)

    await Tortoise.close_connections()

if __name__ == "__main__":
    run_async(convert_database())
