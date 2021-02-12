import os
import sqlite3


dbpath = os.path.abspath('./database/save.db')
conn = sqlite3.connect(dbpath)
c = conn.cursor()
c.execute('''CREATE TABLE time
       (ID INT PRIMARY KEY     NOT NULL,
       NAME  TEXT NOT NULL,
       TIME TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')
c.close()
