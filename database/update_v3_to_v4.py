import os
import sqlite3

from database import BotDBUtil

old_db_link = os.path.abspath('./database/old.db')
conn = sqlite3.connect(old_db_link)
c = conn.cursor()
friends = c.execute(f"SELECT * FROM friend_permission").fetchall()
for friend in friends:
    BotDBUtil.Module(f'QQ|{friend[0]}').enable('|'.split(friend[1]))
groups = c.execute(f"SELECT * FROM group_permission").fetchall()
for group in groups:
    BotDBUtil.Module(f'QQ|Group|{group[0]}').enable('|'.split(group[1]))
group_admins = c.execute(f"SELECT * FROM group_adminuser").fetchall()
for x in group_admins:
    BotDBUtil.SenderInfo(f'QQ|{x[1]}').add_TargetAdmin(f'QQ|Group|{x[2]}')
