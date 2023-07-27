from core.component import module
from core.builtins import Bot, Image, Plain
from core.utils.http import download_to_cache
import sqlite3
import ujson as json
import shutil

cave = module("cave", desc="{cave.help.desc}", developers=["bugungu"])

def open_connection():
    return sqlite3.connect("./modules/cave/data/save.db")

def close_connection(con):
    con.commit()
    con.close()

@cave.command("add {{cave.help.add}}")
async def add(msg: Bot.MessageSession):
    con = open_connection()
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS Caves(ID INTEGER, Sender TEXT, Content TEXT, Unused INTEGER)")
    add = await msg.waitNextMessage(msg.locale.t("cave.msg.add"), delete=True)
    response = await add.toMessageChain()
    cur.execute("SELECT MAX(ID) FROM Caves")
    result = cur.fetchone()
    id = result[0] + 1 if result[0] is not None else 1
    write_json = {"content": []}
    image_count = 0
    for v in response.value:
        if isinstance(v, Image):
            i = v.path
            image_name = f"{id}_{image_count+1}"
            image_count += 1
            image_path = await download_to_cache(i, image_name)
            shutil.copy(image_path, "./modules/cave/data")
            write_json["content"].append(
                {"image": f".\\modules\\cave\\data\\{image_name}"}
            )
        if isinstance(v, Plain):
            i = v.text
            write_json["content"].append({"text": i})
    if not write_json["content"]:
        await msg.finish(msg.locale.t("cave.msg.no_content"))
    content = json.dumps(write_json)
    cur.execute("INSERT INTO Caves VALUES(?,?,?,?)", (id, msg.target.senderName, content, 0))
    close_connection(con)
    await msg.finish(msg.locale.t("cave.msg.done", id=str(id)))

@cave.command("delete <id> {{cave.help.delete}}", required_superuser=True)
async def delete(msg: Bot.MessageSession):
    con = open_connection()
    cur = con.cursor()
    id = int(msg.parsed_msg['<id>'])
    cur.execute("SELECT ID FROM Caves")
    id_list = [item[0] for item in cur.fetchall()]
    if id not in id_list:
        await msg.finish(msg.locale.t("cave.msg.unknown"))
    cur.execute("DELETE FROM Caves WHERE ID = ?",(id,))
    close_connection(con)
    await msg.finish(msg.locale.t("cave.msg.delete", id=str(id)))

@cave.command("list {{cave.help.list}}", required_superuser=True)
async def list(msg: Bot.MessageSession):
    con = open_connection()
    cur = con.cursor()
    cur.execute("SELECT ID FROM Caves")
    id_list = [item[0] for item in cur.fetchall()]
    close_connection(con)
    await msg.finish(msg.locale.t("cave.msg.list", id_list=str(id_list)))

@cave.command()
@cave.command("[<id>] {{cave.help.get}}")
async def get(msg: Bot.MessageSession):
    con = open_connection()
    cur = con.cursor()
    try:
        id = int(msg.parsed_msg["<id>"])
        cur.execute("SELECT ID FROM Caves WHERE ID = ?", (id,))
        if not cur.fetchone():
            await msg.finish(msg.locale.t("cave.msg.unknown"))
    except (ValueError, TypeError):
        cur.execute("SELECT ID, Sender, Content FROM Caves ORDER BY RANDOM() LIMIT 1")
        result = cur.fetchone()
        id, sender, content = result[0], result[1], result[2]
    send_msg = []
    send_msg.append(Plain(f"{msg.locale.t('cave.msg.name')} #{id}"))
    data_json = json.loads(content)
    for i in data_json["content"]:
        try:
            send_msg.append(Plain(i["text"]))
        except KeyError:
            send_msg.append(Image(i["image"]))
    send_msg.append(Plain(f"——{sender}\n{msg.locale.t('cave.msg.recall')}"))
    send = await msg.sendMessage(send_msg)
    close_connection(con)
    await msg.sleep(90)
    await send.delete()
    await msg.finish()
