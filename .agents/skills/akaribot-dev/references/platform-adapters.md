# 平台适配器开发

## 目录

- [适配器文件结构](#81-适配器文件结构)
- [平台标识](#82-infopy)
- [Features 能力实例](#83-featurespy)
- [消息入口](#84-botpy)
- [ContextManager 实现](#85-contextpy)
- [启用适配器](#86-启用适配器)

开始适配器改动前，同时读取主技能直接链接的 `architecture.md` 和 `messaging-and-parser.md`；若涉及配置、JobQueue 或 loader，再读取 `infrastructure.md`。不要把其他 reference 当作唯一入口，路由以主 `SKILL.md` 为准。

---

## 8. 平台适配器开发

### 8.1 适配器文件结构

```
bots/{platform}/
├── bot.py          # 入口，注册和消息处理
├── context.py      # ContextManager 实现
├── features.py     # 平台能力声明
├── info.py         # 平台标识常量
├── client.py       # SDK 客户端（可选）
├── config.py       # 平台配置（可选）
└── utils.py        # 工具函数（可选）
```

### 8.2 info.py

```python
# bots/my_platform/info.py
client_name = "MyPlatform"

sender_prefix = f"{client_name}|User"
sender_prefix_list = [sender_prefix]

target_group_prefix = f"{client_name}|Group"
target_private_prefix = f"{client_name}|Private"
target_prefix_list = [target_group_prefix, target_private_prefix]
```

`sender_prefix_list` 与 `target_prefix_list` 是**必需**的：`core/client/init.py` 登记客户端时要用它们来判断某个 ID 属于哪个平台。中间那几个具体前缀的命名各平台并不统一（onebot / milky 用 `target_group_prefix` + `target_private_prefix`，discord 用 `target_channel_prefix` / `target_dm_channel_prefix` / `target_guild_prefix`，web 只有一个 `target_prefix`），按自己平台的场景类型取名即可，只要都收进 `target_prefix_list`。

### 8.3 features.py

```python
# bots/my_platform/features.py
from attrs import evolve

from core.builtins.session.features import Features


features = Features(
    support_image=True,
    support_mention=True,
    support_embed=True,
    support_delete=True,
    support_quote=True,
    support_rss=True,
    support_typing=True,
    support_wait=True,
)

# 同平台不同入口需要微调能力时，从实例复制
slash_features = evolve(features, require_enable_modules=False)
```

### 8.4 bot.py

```python
# bots/my_platform/bot.py
from core.builtins.bot import Bot
from core.builtins.session.info import SessionInfo
from .info import client_name, sender_prefix_list, target_prefix_list
from .context import MyPlatformContextManager, MyPlatformFetchedContextManager

Bot.register_bot(client_name=client_name)
ctx_id = Bot.register_context_manager(MyPlatformContextManager)
# 主动推送（post_message / fetch_target）走的是 fetch_session 这一路，必须一并注册
Bot.register_context_manager(MyPlatformFetchedContextManager, fetch_session=True)

async def message_handler(event):
    target_id = f"{target_group_prefix}|{event.group_id}"
    sender_id = f"{client_name}|{event.user_id}"

    session = await SessionInfo.assign(
        target_id=target_id,
        sender_id=sender_id,
        target_from=client_name,
        client_name=client_name,
    )

    await Bot.process_message(session, event)
```

传给 `process_message()` 的 `ctx` 要能支撑后续的平台操作。SDK 的 event 对象在跨越等待后可能失效，部分适配器为此传入自己的快照对象（如 `bots/telegram/bot.py` 的 `TelegramContextSnapshot`），写新适配器时可参考。

### 8.5 context.py

```python
# bots/my_platform/context.py
from core.builtins.session.context import ContextManager

from .features import features as platform_features


class MyPlatformContextManager(ContextManager):
    context: dict[str, Any] = {}
    features = platform_features

    # 17 个抽象方法一个都不能少，不支持的能力写 pass 并在 Features 实例里置 False
    @classmethod
    async def check_native_permission(cls, session_info) -> bool: ...

    @classmethod
    async def check_bot_state(cls, session_info) -> BotState: ...

    @classmethod
    async def send_message(cls, session_info, message, quote=True, **kwargs) -> list[str]:
        # 将 MessageChain 转换为平台格式并发送，返回 message_id 列表
        ...

    @classmethod
    async def send_private_msg(cls, session_info, user_id, message, **kwargs) -> list[str]:
        # 无法私信或发送失败时吞掉平台异常并返回 []
        ...

    @classmethod
    async def delete_message(cls, session_info, message_id, **kwargs) -> None: ...

    @classmethod
    async def restrict_member(cls, session_info, user_id, duration, **kwargs) -> None: ...

    @classmethod
    async def unrestrict_member(cls, session_info, user_id) -> None: ...

    @classmethod
    async def kick_member(cls, session_info, user_id, reason=None) -> None: ...

    @classmethod
    async def ban_member(cls, session_info, user_id, reason=None) -> None: ...

    @classmethod
    async def unban_member(cls, session_info, user_id) -> None: ...

    @classmethod
    async def grant_permission_group(cls, session_info, ...) -> None: ...

    @classmethod
    async def revoke_permission_group(cls, session_info, ...) -> None: ...

    @classmethod
    async def add_reaction(cls, session_info, message_id, emoji) -> None: ...

    @classmethod
    async def remove_reaction(cls, session_info, message_id, emoji) -> None: ...

    @classmethod
    async def start_typing(cls, session_info) -> None: ...

    @classmethod
    async def end_typing(cls, session_info) -> None: ...

    @classmethod
    async def error_signal(cls, session_info) -> None: ...
```

写新适配器时最省事的做法是抄一个能力最接近的现成实现（`bots/telegram/context.py` 结构清晰、`bots/discord/context.py` 覆盖能力最全）。

### 8.6 启用适配器

在 `config/bot_my_platform.toml` 中添加：

```toml
[bot_my_platform]
enable = true
# 平台特定配置
```

---

