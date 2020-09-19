import json

import requests


def checkuser(path, username):
    url = 'https://' + path + '.gamepedia.com/api.php?action=query&list=users&ususers=' + username + '&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
    q = requests.get(url)
    file = json.loads(q.text)
    if ('missing' in file['query']['users'][0]):
        return False
    else:
        return True
