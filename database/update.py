from database.orm import Session
from database.tables import EnabledModules
import ujson as json


session = Session.session

q = session.query(EnabledModules).all()
for x in q:
    x.enabledModules = json.dumps(x.enabledModules.split('|'))
    session.commit()

