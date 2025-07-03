import json
import os

from core.constants.path import bots_path

if __name__ == "__main__":
    bots_list = os.listdir(bots_path)
    i_lst = []
    for i in bots_list:
        p = os.path.join("bots", i)
        if os.path.isdir(p):
            if "bot.py" in os.listdir(p):
                i_lst.append(p.replace("\\", "/"))
    with open("assets/bots_list.json", "w") as f:
        f.write(json.dumps(i_lst))
