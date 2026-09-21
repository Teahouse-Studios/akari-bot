"""数据库格式转换脚本。"""

import os
import sys

from tortoise import run_async, Tortoise
from tortoise.models import Model

if __name__ == "__main__":
    sys.path.append(os.getcwd())

from core.constants.version import database_version
from core.database import fetch_module_db
from core.database.link import get_db_link
from core.database.models import *
from core.logger import Logger
from core.utils.url_audit import GlobalURLAllowlist, GlobalURLBlocklist
from modules.cytoid.database.models import *
from modules.maimai.database.models import *
from modules.phigros.database.models import *
from modules.wiki.database.models import *
from modules.wikilog.database.models import *


# 这些类定义旧数据库的模式，用于连接到旧的数据库表进行数据迁移


class SenderInfoL(Model):
    id = fields.CharField(max_length=512, primary_key=True)
    isInBlockList = fields.BooleanField(default=False)
    isInAllowList = fields.BooleanField(default=False)
    isSuperUser = fields.BooleanField(default=False)
    warns = fields.IntField(default=0)
    disableTyping = fields.BooleanField(default=False)
    petal = fields.IntField(default=0)

    class Meta:
        table = "_old_SenderInfo"


class TargetInfoL(Model):
    targetId = fields.CharField(max_length=512, primary_key=True)
    enabledModules = fields.JSONField(default=[])
    options = fields.JSONField(default={})
    customAdmins = fields.JSONField(default=[])
    muted = fields.BooleanField(default=False)
    locale = fields.CharField(max_length=512)

    class Meta:
        table = "_old_TargetInfo"


class GroupBlockList(Model):
    targetId = fields.CharField(max_length=512, primary_key=True)

    class Meta:
        table = "_old_GroupBlockList"


class StoredDataL(Model):
    name = fields.CharField(max_length=512, primary_key=True)
    value = fields.CharField(max_length=512)

    class Meta:
        table = "_old_StoredData"


class Analytics(Model):
    id = fields.IntField(primary_key=True)
    moduleName = fields.CharField(max_length=512)
    moduleType = fields.CharField(max_length=512)
    targetId = fields.CharField(max_length=512)
    senderId = fields.CharField(max_length=512)
    command = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField()

    class Meta:
        table = "_old_Analytics"


class UnfriendlyActionsTable(Model):
    id = fields.CharField(max_length=512, primary_key=True)
    targetId = fields.CharField(max_length=512)
    senderId = fields.CharField(max_length=512)
    action = fields.CharField(max_length=512)
    detail = fields.CharField(max_length=512)
    timestamp = fields.DatetimeField()

    class Meta:
        table = "_old_unfriendly_action"


class CytoidBindInfoL(Model):
    targetId = fields.CharField(max_length=512, primary_key=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "_old_module_cytoid_CytoidBindInfo"


class DivingProberBindInfoL(Model):
    targetId = fields.CharField(max_length=512, primary_key=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "_old_module_maimai_DivingProberBindInfo"


class PhigrosBindInfoL(Model):
    targetId = fields.CharField(max_length=512, primary_key=True)
    sessiontoken = fields.CharField(max_length=512)
    username = fields.CharField(max_length=512)

    class Meta:
        table = "_old_module_phigros_PgrBindInfo"


class WikiTargetInfoL(Model):
    targetId = fields.CharField(max_length=512, primary_key=True)
    link = fields.CharField(max_length=512, null=True)
    iws = fields.JSONField(default={})
    headers = fields.JSONField(default={"accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"})
    prefix = fields.CharField(max_length=512, null=True)

    class Meta:
        table = "_old_module_wiki_TargetSetInfo"


class WikiSiteInfoL(Model):
    apiLink = fields.CharField(max_length=512, primary_key=True)
    siteInfo = fields.JSONField(default={})
    timestamp = fields.DatetimeField()

    class Meta:
        table = "_old_module_wiki_WikiInfo"


class WikiAllowListL(Model):
    apiLink = fields.CharField(max_length=512, primary_key=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "_old_module_wiki_WikiAllowList"


class WikiBlockListL(Model):
    apiLink = fields.CharField(max_length=512, primary_key=True)
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "_old_module_wiki_WikiBlockList"


class WikiBotAccountListL(Model):
    apiLink = fields.CharField(max_length=512, primary_key=True)
    botAccount = fields.CharField(max_length=512)
    botPassword = fields.CharField(max_length=512)

    class Meta:
        table = "_old_module_wiki_WikiBotAccountList"


class WikiLogTargetSetInfoL(Model):
    targetId = fields.CharField(max_length=512, primary_key=True)
    infos = fields.TextField()

    class Meta:
        table = "_old_module_wikilog_WikiLogTargetSetInfo"


async def rename_old_tables():
    Logger.warning("Renaming old tables...")
    await Tortoise.init(db_url=get_db_link(), modules={"models": ["core.scripts.convert_database"]})
    conn = Tortoise.get_connection("default")

    # 重命名旧表以避免冲突
    # 使用"_old"前缀排序在列表末尾，便于管理
    try:
        await conn.execute_query("ALTER TABLE SenderUnionInfo RENAME TO _old_SenderInfo;")
        await conn.execute_query("ALTER TABLE TargetUnionInfo RENAME TO _old_TargetInfo;")
        await conn.execute_query("ALTER TABLE GroupBlockList RENAME TO _old_GroupBlockList;")
        await conn.execute_query("ALTER TABLE StoredData RENAME TO _old_StoredData;")
        await conn.execute_query("ALTER TABLE Analytics RENAME TO _old_Analytics;")
        await conn.execute_query("ALTER TABLE unfriendly_action RENAME TO _old_unfriendly_action;")
        await conn.execute_query(
            "ALTER TABLE module_cytoid_CytoidBindInfo RENAME TO _old_module_cytoid_CytoidBindInfo;"
        )
        await conn.execute_query(
            "ALTER TABLE module_maimai_DivingProberBindInfo RENAME TO _old_module_maimai_DivingProberBindInfo;"
        )
        await conn.execute_query("ALTER TABLE module_phigros_PgrBindInfo RENAME TO _old_module_phigros_PgrBindInfo;")
        await conn.execute_query("ALTER TABLE module_wiki_TargetSetInfo RENAME TO _old_module_wiki_TargetSetInfo;")
        await conn.execute_query("ALTER TABLE module_wiki_WikiInfo RENAME TO _old_module_wiki_WikiInfo;")
        await conn.execute_query("ALTER TABLE module_wiki_WikiAllowList RENAME TO _old_module_wiki_WikiAllowList;")
        await conn.execute_query("ALTER TABLE module_wiki_WikiBlockList RENAME TO _old_module_wiki_WikiBlockList;")
        await conn.execute_query(
            "ALTER TABLE module_wiki_WikiBotAccountList RENAME TO _old_module_wiki_WikiBotAccountList;"
        )
        await conn.execute_query(
            "ALTER TABLE module_wikilog_WikiLogTargetSetInfo RENAME TO _old_module_wikilog_WikiLogTargetSetInfo;"
        )
        await conn.execute_query("ALTER TABLE job_queues RENAME TO _old_job_queues;")
        await conn.execute_query("ALTER TABLE DBVersion RENAME TO _old_DBVersion;")
    except Exception:
        # 如果表不存在或其他错误，则忽略（可能已经被重命名）
        pass

    await Tortoise.close_connections()


async def convert_database():
    """执行完整的数据库转换过程。"""
    Logger.warning("Start converting old database...")

    database_list = fetch_module_db()

    # 第一步：重命名旧表
    await rename_old_tables()

    # 第二步：初始化新的数据库架构
    await Tortoise.init(
        db_url=get_db_link(),
        modules={"models": ["core.scripts.convert_database", "core.database.models"] + database_list},
    )
    conn = Tortoise.get_connection("default")

    # 生成新的数据库架构
    await Tortoise.generate_schemas(safe=True)

    Logger.warning("Converting old database data...")

    Logger.info("Converting SenderUnionInfo...")
    sender_info_records = await SenderInfoL.all()
    i = 0
    for r in sender_info_records:
        i += 1
        # 每处理 1000 条记录显示一次进度
        if i % 1000 == 0:
            Logger.info(f"Converting SenderUnionInfo {i}/{len(sender_info_records)}...")
        try:
            # 将旧格式的发送者信息转换为新格式。旧的平台 ID 直接作为 union ID，映射行在最后统一补建。
            await SenderUnionInfo.create(
                union_id=r.id,
                blocked=r.isInBlockList,
                trusted=r.isInAllowList,
                superuser=r.isSuperUser,
                warns=r.warns,
                petal=r.petal,
                sender_data={"typing_prompt": not r.disableTyping},
            )
        except Exception as e:
            Logger.error(f"Failed to convert SenderUnionInfo: {r.id}, error: {e}")
            Logger.error(f"SenderUnionInfo record: {r.__dict__}")
    # 删除旧表
    await conn.execute_query("DROP TABLE IF EXISTS _old_SenderInfo;")

    Logger.info("Converting TargetUnionInfo...")

    # 获取所有场景信息和黑名单信息
    target_info_records = await TargetInfoL.all()
    group_block_records = await GroupBlockList.all()
    # 创建黑名单 ID 集合，便于后续查询
    blocked_target_ids = {record.targetId for record in group_block_records}
    i = 0
    for r in target_info_records:
        i += 1
        if i % 1000 == 0:
            Logger.info(f"Converting TargetUnionInfo {i}/{len(target_info_records)}...")
        try:
            # 将旧格式的场景信息转换为新格式。旧的平台 ID 直接作为 union ID，映射行在最后统一补建。
            await TargetUnionInfo.create(
                union_id=r.targetId,
                blocked=False,
                muted=r.muted,
                locale=r.locale,
                modules=r.enabledModules,
                custom_admins=r.customAdmins,
                target_data=r.options,
            )
        except Exception as e:
            Logger.error(f"Failed to convert TargetUnionInfo: {r.targetId}, error: {e}")
            Logger.error(f"TargetUnionInfo record: {r.__dict__}")

        # 如果场景在黑名单中，更新其 blocked 字段
        if r.targetId in blocked_target_ids:
            try:
                target_info_record = await TargetUnionInfo.get_by_target_id(r.targetId, create=False)
                if target_info_record:
                    target_info_record.blocked = True
                    await target_info_record.save()
                else:
                    await TargetUnionInfo.create(union_id=r.targetId, blocked=True)
            except Exception as e:
                Logger.error(f"Failed to convert TargetUnionInfo: {r.targetId}, error: {e}")
                Logger.error(f"TargetUnionInfo record: {r.__dict__}")
    # 删除旧表
    await conn.execute_query("DROP TABLE IF EXISTS _old_GroupBlockList;")

    Logger.info("Converting StoredData...")

    # 转换存储数据，处理 JSON 格式
    stored_data_records = await StoredDataL.all()
    for r in stored_data_records:
        v = r.value.strip()
        # 确保值是 JSON 数组格式
        if not (v.startswith("[") and v.endswith("]")):
            v = f"[{v}]"
        try:
            try:
                # 解析 JSON 值
                v = orjson.loads(v)
            except orjson.JSONDecodeError:
                # 如果 JSON 解析失败则跳过此项
                continue

            await StoredData.create(stored_key=r.name, value=v)
        except Exception as e:
            Logger.error(f"Failed to convert StoredData: {r.name}, error: {e}")
            Logger.error(f"StoredData record: {r.__dict__}")
    # 删除旧表
    await conn.execute_query("DROP TABLE IF EXISTS _old_TargetInfo;")
    await conn.execute_query("DROP TABLE IF EXISTS _old_StoredData;")

    Logger.info("Converting Analytics...")

    # 转换分析数据
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
                target_union_id=r.targetId,
                sender_union_id=r.senderId,
                command=r.command,
                timestamp=r.timestamp,
            )
        except Exception as e:
            Logger.error(f"Failed to convert Analytics: {r.id}, error: {e}")
            Logger.error(f"Analytics record: {r.__dict__}")
    await conn.execute_query("DROP TABLE IF EXISTS _old_Analytics;")

    Logger.info("Converting UnfriendlyActions...")

    # 转换不友好行为记录
    unfriendly_action_record = await UnfriendlyActionsTable.all()
    for r in unfriendly_action_record:
        try:
            await UnfriendlyActionRecords.create(
                id=r.id,
                target_id=r.targetId,
                sender_id=r.senderId,
                target_union_id=r.targetId,
                sender_union_id=r.senderId,
                timestamp=r.timestamp,
                action=r.action,
                detail=r.detail,
            )
        except Exception as e:
            Logger.error(f"Failed to convert UnfriendlyActionRecords: {r.id}, error: {e}")
            Logger.error(f"UnfriendlyActionRecords record: {r.__dict__}")
    await conn.execute_query("DROP TABLE IF EXISTS _old_unfriendly_action;")

    Logger.info("Converting CytoidBindInfo...")

    # Cytoid 模块：绑定信息转换
    cytoid_bind_record = await CytoidBindInfoL.all()
    for r in cytoid_bind_record:
        try:
            await CytoidBindInfo.create(
                union_id=r.targetId,
                username=r.username,
            )
        except Exception as e:
            Logger.error(f"Failed to convert CytoidBindInfo: {r.targetId}, error: {e}")
            Logger.error(f"CytoidBindInfo record: {r.__dict__}")
    await conn.execute_query("DROP TABLE IF EXISTS _old_module_cytoid_CytoidBindInfo;")

    Logger.info("Converting DivingProberBindInfo...")

    # Maimai 模块：绑定信息转换
    maimai_bind_record = await DivingProberBindInfoL.all()
    for r in maimai_bind_record:
        try:
            await DivingProberBindInfo.create(
                union_id=r.targetId,
                username=r.username,
            )
        except Exception as e:
            Logger.error(f"Failed to convert DivingProberBindInfo: {r.targetId}, error: {e}")
            Logger.error(f"DivingProberBindInfo record: {r.__dict__}")
    await conn.execute_query("DROP TABLE IF EXISTS _old_module_maimai_DivingProberBindInfo;")

    Logger.info("Converting PhigrosBindInfo...")

    # Phigros 模块：绑定信息转换
    phigros_bind_record = await PhigrosBindInfoL.all()
    for r in phigros_bind_record:
        try:
            await PhigrosBindInfo.create(
                union_id=r.targetId,
                session_token=r.sessiontoken,
                username=r.username,
            )
        except Exception as e:
            Logger.error(f"Failed to convert PhigrosBindInfo: {r.targetId}, error: {e}")
            Logger.error(f"PhigrosBindInfo record: {r.__dict__}")
    await conn.execute_query("DROP TABLE IF EXISTS _old_module_phigros_PgrBindInfo;")

    Logger.info("Converting WikiTargetInfo...")

    # Wiki 模块：场景设置转换
    wiki_target_info_record = await WikiTargetInfoL.all()
    for r in wiki_target_info_record:
        try:
            await WikiTargetInfo.create(
                union_id=r.targetId,
                api_link=r.link,
                interwikis=r.iws,
                headers=r.headers,
                prefix=r.prefix,
            )
        except Exception as e:
            Logger.error(f"Failed to convert WikiTargetInfo: {r.targetId}, error: {e}")
            Logger.error(f"WikiTargetInfo record: {r.__dict__}")
    await conn.execute_query("DROP TABLE IF EXISTS _old_module_wiki_TargetSetInfo;")

    Logger.info("Converting WikiSiteInfo...")

    # Wiki 网站信息转换
    wiki_site_info_record = await WikiSiteInfoL.all()
    for r in wiki_site_info_record:
        try:
            await WikiSiteInfo.create(api_link=r.apiLink, site_info=r.siteInfo, timestamp=r.timestamp)
        except Exception as e:
            Logger.error(f"Failed to convert WikiSiteInfo: {r.apiLink}, error: {e}")
            Logger.error(f"WikiSiteInfo record: {r.__dict__}")
    await conn.execute_query("DROP TABLE IF EXISTS _old_module_wiki_WikiInfo;")

    Logger.info("Converting WikiAllowList to the global URL allowlist...")

    # 旧 Wiki API 白名单已并入全局 URL 规则文件；全部写入成功后才删除旧表。
    wiki_allow_list_record = await WikiAllowListL.all()
    GlobalURLAllowlist.import_user_rules(r.apiLink for r in wiki_allow_list_record)
    await conn.execute_query("DROP TABLE IF EXISTS _old_module_wiki_WikiAllowList;")

    Logger.info("Converting WikiBlockList to the global URL blocklist...")

    # 旧 Wiki API 黑名单同样保留精确规则或 regex: 前缀的正则规则。
    wiki_block_list_record = await WikiBlockListL.all()
    GlobalURLBlocklist.import_user_rules(r.apiLink for r in wiki_block_list_record)
    await conn.execute_query("DROP TABLE IF EXISTS _old_module_wiki_WikiBlockList;")

    Logger.info("Converting WikiBotAccountList...")

    # Wiki 机器人账号转换
    wiki_account_list_record = await WikiBotAccountListL.all()
    for r in wiki_account_list_record:
        try:
            await WikiBotAccountList.create(api_link=r.apiLink, bot_account=r.botAccount, bot_password=r.botPassword)
        except Exception as e:
            Logger.error(f"Failed to convert WikiBotAccountList: {r.apiLink}, error: {e}")
            Logger.error(f"WikiBotAccountList record: {r.__dict__}")
    await conn.execute_query("DROP TABLE IF EXISTS _old_module_wiki_WikiBotAccountList;")

    Logger.info("Converting WikiLogTargetSetInfo...")

    # WikiLog 场景设置转换
    wikilog_target_set_info_record = await WikiLogTargetSetInfoL.all()
    for r in wikilog_target_set_info_record:
        try:
            await WikiLogTargetSetInfo.create(union_id=r.targetId, infos=orjson.loads(r.infos))
        except Exception as e:
            Logger.error(f"Failed to convert WikiLogTargetSetInfo: {r.targetId}, error: {e}")
            Logger.error(f"WikiLogTargetSetInfo record: {r.__dict__}")
    await conn.execute_query("DROP TABLE IF EXISTS _old_module_wikilog_WikiLogTargetSetInfo;")

    Logger.info("Building union binds...")

    # 旧库中数据与平台 ID 一一对应，转换后 union ID 即为原 ID，据此补建映射行。
    await backfill_union_binds()

    Logger.info("Converting DBVersion...")

    # 更新数据库版本信息
    db_v = await DBVersion.first()
    if db_v:
        await db_v.delete()
    await DBVersion.create(version=database_version)
    # 清理任务队列表
    await conn.execute_query("DROP TABLE IF EXISTS _old_job_queues;")
    await conn.execute_query("DROP TABLE IF EXISTS _old_DBVersion;")

    # 关闭数据库连接
    await Tortoise.close_connections()


if __name__ == "__main__":
    run_async(convert_database())
