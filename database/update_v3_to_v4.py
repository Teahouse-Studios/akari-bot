import base64
import os
import re
import sqlite3

from database import BotDBUtil
from modules.wiki.dbutils import WikiTargetInfo

old_db_link = os.path.abspath('./database/old.db')
conn = sqlite3.connect(old_db_link)
c = conn.cursor()
friends = c.execute(f"SELECT * FROM friend_permission").fetchall()
for friend in friends:
    BotDBUtil.Module(f'QQ|{friend[0]}').enable(friend[1].split('|'))
groups = c.execute(f"SELECT * FROM group_permission").fetchall()
for group in groups:
    BotDBUtil.Module(f'QQ|Group|{group[0]}').enable(group[1].split('|'))
group_admins = c.execute(f"SELECT * FROM group_adminuser").fetchall()
for group_admin in group_admins:
    BotDBUtil.SenderInfo(f'QQ|{group_admin[1]}').add_TargetAdmin(f'QQ|Group|{group_admin[2]}')
superusers = c.execute(f"SELECT * FROM superuser").fetchall()
for superuser in superusers:
    BotDBUtil.SenderInfo(f'QQ|{superuser[0]}').edit("isSuperUser", True)
c.close()
conn.close()
old_wikidb_link = os.path.abspath('./database/wiki_old.db')
conn = sqlite3.connect(old_wikidb_link)
c = conn.cursor()
wiki_friends_start = c.execute(f"SELECT * FROM start_wiki_link_Friend").fetchall()
for friend_start in wiki_friends_start:
    WikiTargetInfo(f'QQ|{friend_start[0]}').add_start_wiki(friend_start[1])
wiki_groups_start = c.execute(f"SELECT * FROM start_wiki_link_Group").fetchall()
for group_start in wiki_groups_start:
    WikiTargetInfo(f'QQ|Group|{group_start[0]}').add_start_wiki(group_start[1])
wiki_friends_custom = c.execute(f"SELECT * FROM custom_interwiki_Friend").fetchall()
for friend_custom in wiki_friends_custom:
    for y in friend_custom[1].split('|'):
        z = y.split('>')
        if len(z) > 1:
            WikiTargetInfo(f'QQ|{friend_custom[0]}').config_interwikis(z[0], z[1], True)
wiki_groups_custom = c.execute(f"SELECT * FROM custom_interwiki_Group").fetchall()
for group_custom in wiki_groups_custom:
    for y in group_custom[1].split('|'):
        z = y.split('>')
        if len(z) > 1:
            WikiTargetInfo(f'QQ|Group|{group_custom[0]}').config_interwikis(z[0], z[1], True)
wiki_groups_headers = c.execute(f"SELECT * FROM request_headers_group").fetchall()
for headers_group in wiki_groups_headers:
    headers = {}
    headerd = str(base64.decodebytes(headers_group[1]).decode('utf-8'))
    headersp = headerd.split('\n')
    for x in headersp:
        if x != '':
            x = x.split(':')
            headers[x[0]] = re.sub(r'^ ', '', x[1])
    WikiTargetInfo(f'QQ|Group|{headers_group[0]}').config_headers(headers, let_it=True)
wiki_friends_headers = c.execute(f"SELECT * FROM request_headers_friend").fetchall()
for headers_friend in wiki_friends_headers:
    headers = {}
    headerd = str(base64.decodebytes(headers_friend[1]).decode('utf-8'))
    headersp = headerd.split('\n')
    for x in headersp:
        if x != '':
            x = x.split(':')
            headers[x[0]] = re.sub(r'^ ', '', x[1])
    WikiTargetInfo(f'QQ|{headers_friend[0]}').config_headers(headers, let_it=True)
