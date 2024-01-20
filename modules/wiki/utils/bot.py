import aiohttp
from core.logger import Logger
from .dbutils import BotAccount as BotAccountDB


class LoginFailed(Exception):
    pass


class BotAccount:
    cookies = {}

    @staticmethod
    async def _login(api_link, account, password):
        lgtoken_url = f'{api_link}?action=query&meta=tokens&type=login&format=json'
        PARAMS_1 = {
            'action': "login",
            'lgname': account,
            'lgpassword': password,
            'format': "json"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(lgtoken_url) as req:
                if req.status != 200:
                    raise LoginFailed(f'Login failed: {await req.text()}')
                PARAMS_1['lgtoken'] = (await req.json())['query']['tokens']['logintoken']
            async with session.post(api_link, data=PARAMS_1) as req:
                if req.status != 200:
                    raise LoginFailed(f'Login failed: {await req.text()}')
                Logger.info(f'Logged in to {api_link} as {account}')
                return req.cookies.output(attrs=[], header='', sep=';')

    @classmethod
    async def login(cls):
        accounts = BotAccountDB.get_all()
        for account in accounts:
            try:
                cls.cookies[account.apiLink] = await BotAccount._login(account.apiLink,
                                                                       account.botAccount,
                                                                       account.botPassword)

            except LoginFailed as e:
                Logger.error(f'Login failed: {e}')
