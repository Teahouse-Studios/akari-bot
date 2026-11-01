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

# SDK 的 App 在每个进程内只允许存在一个实例，连接参数由 bot_satori 配置决定。
satori_app = App(websockets_info)
