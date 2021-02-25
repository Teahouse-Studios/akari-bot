import os
import sqlite3

dbpath = os.path.abspath('./database/save.db')
conn = sqlite3.connect(dbpath)
c = conn.cursor()
c.execute('''CREATE TABLE friend_permission
       (ID INT PRIMARY KEY     NOT NULL,
       ENABLE_MODULES  TEXT);''')
c.close()
