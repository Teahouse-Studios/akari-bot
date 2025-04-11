import json
import os

from core.constants import modules_path, schedulers_path, bots_path

if __name__ == "__main__":
    modules_folder_list = os.listdir(modules_path)
    with open("assets/modules_list.json", "w") as f:
        f.write(json.dumps(modules_folder_list))
    schedulers_folder_list = os.listdir(schedulers_path)
    with open("assets/schedulers_list.json", "w") as f:
        f.write(json.dumps(schedulers_folder_list))
    slash_list = os.listdir("bots/discord/slash")
    with open("assets/discord_slash_list.json", "w") as f:
        f.write(json.dumps(slash_list))
    bots_list = os.listdir(bots_path)
    i_lst = []
    for i in bots_list:
        p = os.path.join("bots", i)
        if os.path.isdir(p):
            if "bot.py" in os.listdir(p):
                i_lst.append(p.replace("\\", "/"))
    with open("assets/bots_list.json", "w") as f:
        f.write(json.dumps(i_lst))
    database_list = []
    for file_name in modules_folder_list:
        if os.path.isdir(os.path.join(modules_path, file_name)):
            if os.path.exists(
                os.path.join(modules_path, file_name, "database/models.py")
            ):
                database_list.append(f"modules.{file_name}.database.models")
    with open("assets/database_list.json", "w") as f:
        f.write(json.dumps(database_list))
