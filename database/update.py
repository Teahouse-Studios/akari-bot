import ujson as json

from database import BotDBUtil
from database.orm import Session
from database.tables import DBVersion, TargetInfo


def update_database():
    engine = Session.engine
    session = Session.session
    version = session.query(DBVersion).first()
    value = int(version.value)
    if value == 1:
        TargetInfo.__table__.drop(engine)
        TargetInfo.__table__.create(engine)
        q = session.execute("SELECT * FROM enabledModules")
        for v in q.fetchall():
            data = BotDBUtil.TargetInfo(v[0]).init()
            data.enabledModules = v[1]
            session.commit()

        q = session.execute("SELECT * FROM targetOptions")
        for v in q.fetchall():
            data = BotDBUtil.TargetInfo(v[0]).init()
            data.options = v[1]
            session.commit()

        q = session.execute("SELECT * FROM mutelist")
        for v in q.fetchall():
            data = BotDBUtil.TargetInfo(v[0]).init()
            data.muted = True
            session.commit()

        q = session.execute("SELECT * FROM targetadmin")
        for v in q.fetchall():
            data = BotDBUtil.TargetInfo(v[2]).init()
            custom_admins = json.loads(data.custom_admins)
            custom_admins.append(v[1])
            data.custom_admins = json.dumps(custom_admins)
            session.commit()

        session.execute("DROP TABLE IF EXISTS enabledModules, targetOptions, mutelist, targetadmin")

        version.value = '2'
        session.commit()
