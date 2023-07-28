from core.component import module
from core.builtins import Bot, Image, Plain
from core.utils.http import download_to_cache
from .data.dbutils import CavesHandler
import shutil

cave = module("cave", desc="{cave.help.desc}", developers=["bugungu"])


@cave.command("add {{cave.help.add}}")
async def add(msg: Bot.MessageSession):
    add = await msg.waitNextMessage(msg.locale.t("cave.msg.add"), delete=True)
    response = await add.toMessageChain()
    ca = CavesHandler()
    id = ca.get_id()
    cave_data = {"id": id, "sender": msg.target.senderName, "content": []}
    image_count = 0
    for msg_part in response.value:
        if isinstance(msg_part, Image):
            image_name = f"{id}_{image_count+1}"
            image_path = await download_to_cache(msg_part.path, f"{id}_{image_count+1}")
            shutil.copy(image_path, "./modules/cave/data")
            cave_data["content"].append(
                {"image": f".\\modules\\cave\\data\\{image_name}"}
            )
            image_count += 1
        elif isinstance(msg_part, Plain):
            cave_data["content"].append({"text": msg_part.text})
    if not cave_data["content"]:
        await msg.finish(msg.locale.t("cave.msg.no_content"))
    if ca.add_cave(cave_data):
        await msg.finish(msg.locale.t("cave.msg.done", id=str(id)))

@cave.command("remove <id> {{cave.help.delete}}", required_superuser=True)
@cave.command("delete <id> {{cave.help.delete}}", required_superuser=True)
async def delete(msg: Bot.MessageSession):
    ca = CavesHandler()
    id = int(msg.parsed_msg["<id>"])
    if ca.delete_cave(id):
        await msg.finish(msg.locale.t("cave.msg.delete", id=str(id)))
    await msg.finish(msg.locale.t("cave.msg.unknown"))


@cave.command("list {{cave.help.list}}", required_superuser=True)
async def list_caves(msg: Bot.MessageSession):
    ca = CavesHandler()
    id_list = ca.cave_list()
    if id_list is None:
        await msg.finish(msg.locale.t("cave.msg.unknown"))    
    await msg.finish(msg.locale.t("cave.msg.list", id_list=id_list))
    

@cave.command()
@cave.command("[<id>] {{cave.help.get}}")
async def get_cave(msg: Bot.MessageSession):
    try:
        id = int(msg.parsed_msg["<id>"])
    except (ValueError, TypeError):
        id = None
    send_msg = []
    ca = CavesHandler(id)
    cave_data = ca.get_cave()
    if cave_data is None:
        await msg.finish(msg.locale.t("cave.msg.unknown"))
    send_msg.append(Plain(f"{msg.locale.t('cave.msg.name')} #{cave_data['id']}"))
    for content in cave_data["content"]:
        if "text" in content:
            send_msg.append(Plain(content["text"]))
        elif "image" in content:
            send_msg.append(Image(content["image"]))
    send_msg.append(
        Plain(f"——{cave_data['sender']}\n{msg.locale.t('cave.msg.recall')}")
    )
    send = await msg.sendMessage(send_msg)
    await msg.sleep(90)
    await send.delete()
    await msg.finish()
