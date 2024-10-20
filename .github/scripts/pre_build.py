import json
import os

if __name__ == "__main__":
    modules_folder_list = os.listdir('modules')
    with open('assets/modules_list.json', 'w') as f:
        json.dump(modules_folder_list, f)
    schedulers_folder_list = os.listdir('schedulers')
    with open('assets/schedulers_list.json', 'w') as f:
        json.dump(schedulers_folder_list, f)
    slash_list = os.listdir('bots/discord/slash')
    with open('assets/discord_slash_list.json', 'w') as f:
        json.dump(slash_list, f)
