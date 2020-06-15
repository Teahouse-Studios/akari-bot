import requests
import json
url = 'https://minecraft.gamepedia.com/api.php?action=query&list=users&ususers=Lightyzh&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
q = requests.get(url)
file = json.loads(q.text)
if ('missing' in file['query']['users'][0]):
    print('t')
else:
    print('f')