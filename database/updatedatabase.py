import os
import sqlite3

dbpath = os.path.abspath('./database/save.db')
conn = sqlite3.connect(dbpath)
c = conn.cursor()
a = c.execute(f"ALTER TABLE group_adminuser RENAME TO group_adminuser_old")
c.execute('''CREATE TABLE group_adminuser
       (ID INTEGER PRIMARY KEY AUTOINCREMENT,
       TID INT,
       TGROUP INT);''')
t = c.execute(f"SELECT * FROM group_adminuser_old").fetchall()
for x in t:
    c.execute(f"INSERT INTO group_adminuser (TID, TGROUP) VALUES (?, ?)", x)
conn.commit()
c.close()
