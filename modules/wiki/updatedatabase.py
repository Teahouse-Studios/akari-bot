import os
import sqlite3

dbpath = os.path.abspath('./save.db')
conn = sqlite3.connect(dbpath)
c = conn.cursor()
c.execute('''CREATE TABLE wiki_info
       (LINK TEXT PRIMARY KEY     NOT NULL,
       SITEINFO  TEXT,
       TS  TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')
c.execute('''CREATE TABLE request_headers_group
       (ID TEXT PRIMARY KEY     NOT NULL,
       HEADERS  TEXT);''')
c.execute('''CREATE TABLE request_headers_self
       (ID TEXT PRIMARY KEY     NOT NULL,
       HEADERS  TEXT);''')
c.close()