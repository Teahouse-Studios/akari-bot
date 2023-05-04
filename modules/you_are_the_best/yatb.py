import requests
from bs4 import BeautifulSoup
import traceback

async def yatb(user_name):
    try:
        url = 'https://api.ltlec.net/nb?name=' + user_name
        strhtml = requests.get(url)
        soup = BeautifulSoup(strhtml.text, 'lxml')
        data = soup.select('body')
        a = ''
        for item in data:
            a = item.get_text()
    except Exception:
        traceback.print_exc()
    return a