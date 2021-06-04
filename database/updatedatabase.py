import os
import sqlite3

dbpath = os.path.abspath('./database/save.db')
conn = sqlite3.connect(dbpath)
c = conn.cursor()
c.execute('''CREATE TABLE group_adminuser
       (ID INT PRIMARY KEY     NOT NULL,
       QGROUP  INT);''')
c.close()
