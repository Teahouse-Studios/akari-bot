import traceback
import os
import sqlite3

dbpath = os.path.abspath('./save.db')
conn = sqlite3.connect(dbpath)
c = conn.cursor()
try:
    a = c.execute(f"ALTER TABLE start_wiki_link_self RENAME TO start_wiki_link_Friend")
except:
    traceback.print_exc()
try:
    a = c.execute(f"ALTER TABLE custom_interwiki_self RENAME TO custom_interwiki_Friend")
except:
    traceback.print_exc()
try:
    a = c.execute(f"ALTER TABLE request_headers_self RENAME TO request_headers_Friend")
except:
    traceback.print_exc()

conn.commit()
