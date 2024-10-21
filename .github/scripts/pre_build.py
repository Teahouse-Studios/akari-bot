import json
import os

if __name__ == "__main__":
    modules_folder_list = os.listdir('modules')
    with open('assets/modules_list.json', 'w') as f:
        f.write(json.dumps(modules_folder_list))
    schedulers_folder_list = os.listdir('schedulers')
    with open('assets/schedulers_list.json', 'w') as f:
        f.write(json.dumps(schedulers_folder_list))
    slash_list = os.listdir('bots/discord/slash')
    with open('assets/discord_slash_list.json', 'w') as f:
        f.write(json.dumps(slash_list))
