import orjson as json
from sqlalchemy import text, update

from core.database import BotDBUtil
from core.database.orm import Session
from core.database.tables import DBVersion, TargetInfoTable, is_mysql, AnalyticsData


def update_database():
    engine = Session.engine
    session = Session.session
    version = session.query(DBVersion).first()
    value = int(version.value)
    if value < 2:
        TargetInfoTable.__table__.drop(engine)
        TargetInfoTable.__table__.create(engine)
        q = session.execute(text("SELECT * FROM enabledModules"))
        for v in q.fetchall():
            data = BotDBUtil.TargetInfo(v[0]).init()
            data.enabledModules = v[1]
            session.commit()

        q = session.execute(text("SELECT * FROM targetOptions"))
        for v in q.fetchall():
            data = BotDBUtil.TargetInfo(v[0]).init()
            data.options = v[1]
            session.commit()

        q = session.execute(text("SELECT * FROM mutelist"))
        for v in q.fetchall():
            data = BotDBUtil.TargetInfo(v[0]).init()
            data.muted = True
            session.commit()

        q = session.execute(text("SELECT * FROM targetadmin"))
        for v in q.fetchall():
            data = BotDBUtil.TargetInfo(v[2]).init()
            custom_admins = json.loads(data.custom_admins)
            custom_admins.append(v[1])
            data.custom_admins = json.dumps(custom_admins)
            session.commit()

        session.execute(
            text(
                "DROP TABLE IF EXISTS enabledModules, targetOptions, mutelist, targetadmin"
            )
        )

        version.value = "2"
        session.commit()
    if value < 3:
        session.execute(
            text("ALTER TABLE TargetInfo ADD column petal INTEGER DEFAULT 0")
        )

        version.value = "3"
        session.commit()
    if value < 4:
        session.execute(text("ALTER TABLE TargetInfo DROP COLUMN petal"))
        session.execute(
            text("ALTER TABLE SenderInfo ADD column petal INTEGER DEFAULT 0")
        )
        session.execute(
            text("ALTER TABLE TargetInfo RENAME COLUMN custom_admins TO customAdmins")
        )
        session.execute(
            text("ALTER TABLE SenderInfo RENAME COLUMN disable_typing TO disableTyping")
        )

        version.value = "4"
        session.commit()
    if value < 5:
        if is_mysql:
            session.execute(
                text(
                    "ALTER TABLE module_wiki_WikiInfo MODIFY COLUMN siteInfo LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
            )
        version.value = "5"
        session.commit()
    if value < 6:
        mappings = []
        i = 0
        for v in session.query(AnalyticsData).all():
            mappings.append({"id": v.id, "command": "*".join(v.command[::2])})
            i += 1
            print(v.id, i)
            if i % 5000 == 0:
                session.execute(update(AnalyticsData), mappings)
                print("done")
                session.commit()
                mappings.clear()
                session.flush()
                i = 0
        session.execute(update(AnalyticsData), mappings)
        mappings.clear()
        session.commit()
        session.flush()
        version.value = "6"
        session.commit()
