import os
import sqlite3

dbpath = os.path.abspath('./save.db')
conn = sqlite3.connect(dbpath)
c = conn.cursor()
a = c.execute(f"SELECT * FROM start_wiki_link_group WHERE LINK='https://minecraft-zh.gamepedia.com/api.php'")
for x in a:
    print(x)
    c.execute(f"UPDATE start_wiki_link_group SET LINK='https://minecraft.fandom.com/zh/api.php' WHERE ID='{x[0]}'")
a = c.execute(f"SELECT * FROM start_wiki_link_group WHERE LINK='https://minecraft-zh.gamepedia.com/api.php/api.php'")
for x in a:
    print(x)
    c.execute(f"UPDATE start_wiki_link_group SET LINK='https://minecraft.fandom.com/zh/api.php' WHERE ID='{x[0]}'")
a = c.execute(f"SELECT * FROM start_wiki_link_self WHERE LINK='https://minecraft-zh.gamepedia.com/api.php'")
for x in a:
    print(x)
    c.execute(f"UPDATE start_wiki_link_self SET LINK='https://minecraft.fandom.com/zh/api.php' WHERE ID='{x[0]}'")
a = c.execute(f"SELECT * FROM start_wiki_link_self WHERE LINK='https://minecraft-zh.gamepedia.com/api.php/api.php'")
for x in a:
    print(x)
    c.execute(f"UPDATE start_wiki_link_self SET LINK='https://minecraft.fandom.com/zh/api.php' WHERE ID='{x[0]}'")
conn.commit()