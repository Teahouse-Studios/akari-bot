import requests
import json
async def checkuser(path,username):
    url = 'https://'+path+'.gamepedia.com/api.php?action=query&list=users&ususers='+username+'&usprop=groups%7Cblockinfo%7Cregistration%7Ceditcount%7Cgender&format=json'
    q = requests.get(url)
    w = json.loads(q.text)
    miss = file['query']['users'][0]['missing']
    if not miss:
        return True
    else:
        return False