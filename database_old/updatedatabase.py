import os
import sqlite3

dbpath = os.path.abspath('./database/save.db')
conn = sqlite3.connect(dbpath)
c = conn.cursor()
a = c.execute(f"SELECT * FROM friend_permission").fetchall()
for x in a:
    enabled_split = x[1].split('|')
    mv = {'mcv_rss_self': 'mcv_rss', 'mcv_jira_rss_self': 'mcv_jira_rss'}
    for y in mv:
        if y in enabled_split:
            enabled_split.remove(y)
            enabled_split.append(mv[y])
            c.execute("UPDATE friend_permission SET ENABLE_MODULES=? WHERE ID=?", ('|'.join(enabled_split), x[0]))
            conn.commit()

a = c.execute(f"SELECT * FROM group_permission").fetchall()
for x in a:
    enabled_split = x[1].split('|')
    mv = {'wiki_regex': 'wiki_inline'}
    for y in mv:
        if y in enabled_split:
            enabled_split.remove(y)
            enabled_split.append(mv[y])
            c.execute("UPDATE group_permission SET ENABLE_MODULES=? WHERE ID=?", ('|'.join(enabled_split), x[0]))
            conn.commit()