import httpx

from core.logger import Logger
from .dbutils import BotAccount as BotAccountDB


class LoginFailed(Exception):
    pass


class BotAccount:
    cookies = {}

    @staticmethod
    async def _login(api_link, account, password):
        lgtoken_url = f"{api_link}?action=query&meta=tokens&type=login&format=json"
        PARAMS_1 = {
            "action": "login",
            "lgname": account,
            "lgpassword": password,
            "format": "json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(lgtoken_url)
            if resp.status_code != 200:
                raise LoginFailed(f"Login failed: {resp.text}")
            PARAMS_1["lgtoken"] = resp.json()["query"]["tokens"]["logintoken"]

            resp = await client.post(api_link, data=PARAMS_1)
            if resp.status_code != 200:
                raise LoginFailed(f"Login failed: {resp.text}")

            Logger.info(f"Logged in to {api_link} as {account}")
            return dict(resp.cookies)

    @classmethod
    async def login(cls):
        accounts = BotAccountDB.get_all()
        for account in accounts:
            try:
                cls.cookies[account.apiLink] = await BotAccount._login(
                    account.apiLink, account.botAccount, account.botPassword
                )

            except LoginFailed as e:
                Logger.error(f"Login failed: {e}")
