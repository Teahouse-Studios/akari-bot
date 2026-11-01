from satori import EventType
from satori.client import App, WebsocketsInfo

from bots.satori.config import SatoriConfig, SatoriSecretConfig

websockets_info = WebsocketsInfo(
    host=SatoriConfig.satori_host,
    port=SatoriConfig.satori_port,
    path=SatoriConfig.satori_path or "",
    token=SatoriSecretConfig.satori_token or None,
    secure=SatoriConfig.satori_secure,
    timeout=SatoriConfig.satori_timeout,
)


class SatoriApp(App):
    async def post(self, event, conn):
        login = event.login
        if (
            login
            and login.user
            and event.type not in (EventType.LOGIN_ADDED, EventType.LOGIN_UPDATED, EventType.LOGIN_REMOVED)
        ):
            for account in self.accounts.values():
                if account.platform == login.platform and str(account.self_id) == str(login.user.id):
                    login.adapter = account.adapter
                    break
        await super().post(event, conn)


# SDK 的 App 在每个进程内只允许存在一个实例，连接参数由 bot_satori 配置决定。
satori_app = SatoriApp(websockets_info)
