# 加载、配置、数据库与队列

## 目录

- [模块加载系统](#55-模块加载系统-coreloaderpy)
- [组件注册系统](#56-组件注册系统-corecomponentpy)
- [配置系统](#57-配置系统-coreconfig)
- [数据库系统](#58-数据库系统-coredatabase)
- [队列系统](#59-队列系统-corequeue)
- [导出系统](#121-导出系统避免循环导入)
- [热重载](#127-热重载)

---

### 5.5 模块加载系统 (`core/loader.py`)

```python
class ModulesManager:
    modules: dict[str, Module] = {}           # 模块名 → Module
    modules_aliases: dict[str, str] = {}      # 别名 → 模块名
    modules_hooks: dict[str, Callable] = {}   # 钩子名 → 函数
    modules_origin: dict[str, str] = {}       # 模块名 → Python 模块路径

    @classmethod
    async def reload_module(cls, module_name)
    # 热重载：移除旧模块 → 重新导入 → 重新注册 → 更新 DB 状态
```

加载流程（`load_modules()`，`core/loader.py:34`）：

1. `pkgutil.iter_modules(modules.__path__)` 发现所有模块
2. `importlib.import_module(f"modules.{subm.name}")` 导入
3. 紧接着尝试导入 `modules.<name>.config`（不存在则静默跳过）
4. 每个模块的 `__init__.py` 在导入时调用 `module()` 完成注册
5. `ModuleStatus.init_modules()` 从数据库恢复启用/禁用状态，写入 `module._db_load`

**单个模块加载失败不会中断整体流程**：异常被捕获后写入 `PrivateData.path / ".cache_loader"`（`core/loader.py:89`），`~module list` 等命令会读取该文件展示错误详情。

### 5.6 组件注册系统 (`core/component.py`)

```python
def module(
    module_name: str,
    alias=None,               # 命令别名（str/list/tuple/dict）
    desc=None,                # 模块描述，用 {I18N:key} 单花括号语法
    recommend_modules=None,   # 推荐一并开启的模块
    developers=None,          # 开发者列表
    required_admin=False,     # 需要群组管理员权限
    base=False,               # 基础模块（强制启用，无法被 ~module disable）
    doc=False,                # 有线上文档
    hidden=False,             # 隐藏模块（不出现在 ~help 列表）
    load=True,                # 是否加载
    rss=False,                # RSS 模块
    required_superuser=False,
    required_base_superuser=False,
    available_for="*",        # 可用平台（"*" = 全部）
    exclude_from="",          # 排除平台
    support_languages=None,
) -> Bind.Module:
```

返回的 `Bind.Module` 提供装饰器：

```python
@my_mod.command("template {{I18N:desc}}", *more_templates,
                options_desc=None, required_admin=False,
                required_superuser=False, required_base_superuser=False,
                available_for="*", exclude_from="", load=True, priority=1)
@my_mod.regex(r"pattern", mode="M", desc="...")   # 注册正则
@my_mod.schedule(trigger)                          # 注册定时任务
@my_mod.hook(name=None)                            # 注册钩子
@my_mod.handle(...)                                # 重载版，自动识别 command/regex/schedule
@my_mod.config(cls=None, secret=False)             # 注册模块配置（已弃用，改用 on_module_config，见 §5.7）
```

### 5.7 配置系统 (`core/config/`)

基于 TOML 的配置系统，支持热重载，核心管理类为 `CFGManager`（`core/config/__init__.py:48`）。

#### 模板声明与读取

配置项在配置模板类中集中定义，业务代码直接通过类属性读取：

```python
# 声明：bots/onebot/config.py
@on_bot_config("onebot")
class AiocqhttpConfig:
    qq_typing_emoji: int = 181

# 取值：bots/onebot/context.py —— 每次属性访问都走 CFGManager.get()，支持热重载
from bots.onebot.config import AiocqhttpConfig

qq_typing_emoji = str(AiocqhttpConfig.qq_typing_emoji)
```

模板类由 `ConfigMeta` 元类接管属性访问（`core/config/decorator.py`），每次读取配置文件中的当前值；访问未声明字段会抛出 `AttributeError`。

四个声明入口均位于 `core/config/decorator.py`：

| 场景 | 写法 | 落在哪 | 模板类 |
|---|---|---|---|
| 表外顶层键 | `@on_base_config()` | `config.toml` 的表外顶层 | `BaseConfig` |
| 核心配置 | `@on_config("config")` / `@on_config("config", secret=True)` | `config.toml` 的 `[config]` / `[secret]` | `CoreConfig` |
| 独立核心配置 | `@on_config("jobqueue")` / `@on_config("jobqueue", secret=True)` | `jobqueue.toml` 的 `[jobqueue]` / `[jobqueue_secret]` | `JobQueueConfig` |
| 平台配置 | `@on_bot_config("onebot")` / `@on_bot_config("onebot", secret=True)` | `[bot_onebot]` / `[bot_onebot_secret]` | `AiocqhttpConfig` 等 |
| 模块配置 | `@on_module_config("dice")` / `@on_module_config("dice", secret=True)` | `[module_dice]` / `[module_dice_secret]` | `DiceConfig` 等 |

命名约束（由 `tests/unit/test_config_template.py` 校验）：

- `on_bot_config("<平台名>")` 的平台名须与 `bots/` 下的目录名一致，守护进程按 `bot_<目录名>` 查找 `enable` 开关。
- `on_module_config("<模块名>")` 的模块名须与包内 `module()` 声明一致（主名为连字符且下划线形式作为别名保留时，配置表名可沿用下划线形式）。模块配置统一使用 `on_module_config`，避免 `Bind.Module.config()` 反向导入模块对象引发循环依赖。

核心配置模板按领域分布在 `core/config/`：表外顶层键（如 `default_locale`、`config_version`）位于 `base.py` 的 `BaseConfig`，通用核心项位于 `core.py`，JobQueue、S3 与 WebRender 分别位于 `jobqueue.py`、`s3.py` 和 `webrender.py` 并对应各自的 TOML 文件。调用时直接从所属领域模块导入。

#### 配置初始化与只读约束

`bot.py` 的 `pre_init()` 调用 `core.config.scan.scan_config_templates()` 导入全部配置模板并补全缺失键。随后守护进程设置 `AKARI_CONFIG_READONLY=1` 再启动子进程，**bot 与 server 子进程均为只读**（避免 multiprocessing spawn 重复导入时多进程并发写配置）：

| 方法 | 只读进程中的行为 |
|---|---|
| `CFGManager.write()` / `delete()` / `save()` | 抛 `ConfigOperationError` |
| `CFGManager.get()` 读到缺失的键 | 尝试回写默认值时抛 `ConfigOperationError`；无默认值时返回 `None` |
| `CFGManager.load()` / `watch()` | 正常，热重载不受影响 |
| 配置模板导入 | `__config_fields__` 正常登记，不补写配置文件 |

新增配置项后需重启机器人使 `pre_init()` 补齐配置键。运行期确需修改配置时（如交互式编辑命令、启动期密钥自举），使用显式写接口：

```python
CFGManager.edit_write("jwt_secret", value, secret=True, table_name="bot_web")
CFGManager.edit_delete("some_key", "module_wiki")
```

#### Config() 门面函数与 URL 格式化

`Config()` 仅用于键名在运行时动态确定的场景（不能传 `default` 或 `table_name`）。需要对模板取到的地址补全协议头与尾部斜杠时，使用 `core.config.format_url()`：

```python
from core.config import format_url
from core.config.webrender import WebRenderConfig

remote_web_render_url = format_url(WebRenderConfig.remote_web_render_url)
```

#### 配置注释规范

新增配置字段时，在模板所属组件的 `locales/zh_cn.json`（核心写 `core/`，平台写 `bots/<平台>/`，模块写 `modules/<模块>/`）中添加 `config.comments.<表名>.<字段名>`：

```json
{
    "config.comments.config.typo_check_module_score": "模块拼写检查容许相似度，范围 0 到 1 之间。",
    "config.comments.bot_telegram.enable": "是否开启 Telegram 客户端。"
}
```

- `@on_config("config")` → `config.comments.config.<字段名>`（`secret=True` 时表名为 `secret`）
- `@on_base_config()` → `config.comments.<字段名>`（无表名层级）
- `@on_bot_config("<平台>")` → `config.comments.bot_<平台>.<字段名>`（`secret=True` 时加 `_secret` 后缀）
- `@on_module_config("<模块>")` → `config.comments.module_<模块>.<字段名>`（`secret=True` 时加 `_secret` 后缀）

当单行注释不足以说明多个选项差异时，可通过 `standalone_comments` 在字段前生成多行独立注释块（键为字段名，值为 `zh_cn.json` 中的 i18n 键元组，建议使用 `config.notes.<领域>.<主题>.<说明行>`）：

```python
@on_config(
    "jobqueue",
    standalone_comments={
        "jobqueue_backend": (
            "config.notes.jobqueue.backend.intro",
            "config.notes.jobqueue.backend.database",
            "config.notes.jobqueue.backend.websocket",
        )
    },
)
class JobQueueConfig:
    jobqueue_backend: str = "websocket"
```

配置文件结构：

```
config/
├── config.toml        # 主配置
├── jobqueue.toml      # JobQueue 后端、Peer 与 Hub 配置
├── s3.toml            # S3 兼容对象存储配置
├── webrender.toml     # WebRender 配置
├── bot_onebot.toml    # 平台配置
├── bot_discord.toml   # 平台配置
└── ...
```

### 5.8 数据库系统 (`core/database/`)

使用 Tortoise ORM，支持 SQLite 和 MySQL。所有模型继承 `core/database/base.py` 的 `DBModel`（抽象基类，额外提供 `get_by_target_id(target_id, create=True)`，可以直接传 `MessageSession`）。

**双连接架构**（`init_db()` 里配置两个 Tortoise app）：

| 连接      | app 名         | 模型模块                              | 用途                          |
| --------- | -------------- | ------------------------------------- | ----------------------------- |
| `default` | `models`       | `core.database.models` + 各模块模型   | 主数据库，可配置为 MySQL      |
| `local`   | `local_models` | `core.database.local`                 | 永远本地 SQLite（缓存类数据） |

`local` 里目前只有 `DirtyWordCache`（内容审核结果缓存）和 `CrowdinActivityRecords`。这类数据不该跟着主库走，所以单独放。

**核心模型** (`core/database/models.py`，共 14 个具体模型):

用户与场景的数据挂在 **union**（账号组 / 场景组）上，而不是挂在平台 ID 上，
平台 ID 与 union 之间隔着一张映射表。所以核心表分成两层：

| 层 | 模型 | 主键 | 说明 |
|---|---|---|---|
| 数据层 | `SenderUnionInfo` | `union_id` | 用户组数据（权限、花瓣、`sender_data`），表 `sender_union_info` |
| 数据层 | `TargetUnionInfo` | `union_id` | 场景组数据（模块开关、管理员、语言），表 `target_union_info` |
| 映射层 | `SenderUnionBind` | `sender_id` | 平台账号 → union |
| 映射层 | `TargetUnionBind` | `target_id` | 平台场景 → union，附 `channel_id` |

两个数据层模型继承抽象基类 `UnionInfo`，两个映射层模型继承 `UnionBind`；映射层仅维护平台 ID 到 `union_id` 的归属关系，所有业务状态保存在 `UnionInfo` 上。

其他核心模型：

- `StoredData` - 通用键值存储
- `AnalyticsData` - 命令使用统计（同时记原始 ID 与 union ID）
- `ModuleStatus` - 模块加载状态
- `DBVersion` - 数据库版本
- `UnfriendlyActionRecords` - 违规记录（同时记原始 ID 与 union ID）
- `JobQueuesTable` - 任务队列表（数据库后端的跨进程投递载体）
- `JobQueuePeersTable` - JobQueue Peer 注册表（数据库后端的 Registry）
- `MaliciousLoginRecords` - WebUI 恶意登录记录

**union 解析与约定**：

- 唯一解析入口是 `UnionInfo.resolve_union(平台 ID, create=True)`（查映射表取出数据行，并将映射行挂到 `.bind` 上）。`get_by_target_id()` / `get_by_sender_id()` 是其会话包装，模块表继承 `DBModel` 获得的同名方法也会先解析 union 再查询本表。
- 封禁状态存储在 `UnionInfo.blocked` 上，对组内所有平台 ID 生效：`merge_union` 时 `blocked` 取并集，`unbind_id` 生成的新组会继承原组的 `blocked` 且原位改挂映射行，`bind_id` 拒绝迁移已有映射行的 ID。
- 以 `union_id` 为键的模块表须声明 `union_scope`（`UNION_SCOPE_SENDER` 或 `UNION_SCOPE_TARGET`），以便 `iter_union_models()` 在 union 合并与映射补建时识别其归属域。

**模块数据库**: 模块可在 `database/models.py` 中定义模型，`init_db()` 通过 `fetch_module_db()` 自动发现并注册到 `default` 连接。

**任务队列表迁移**：`core/database/update.py` 在 `db_version < 5` 时会 `DROP TABLE IF EXISTS job_queues` 并按当前模型重建，升级前需停止全部 Bot 与 Server 进程。

### 5.9 队列系统 (`core/queue/`)

可配置后端的 Peer RPC 与信号总线，用于 Client 与 Server 进程间通信。`jobqueue.toml` 的 `[jobqueue].jobqueue_backend` 选择后端实现（`websocket` 为默认推荐项，另可选 `database`），配置通过 `JobQueueConfig` 与 `JobQueueSecretConfig` 读取。后端的 `PeerRegistry` 与 `MessageTransport` 成套装配，连接或鉴权失败时直接终止初始化。切换后端应在停机窗口进行并重启全部进程。主数据库为 SQLite 且选用 `database` 后端时，连接会设置 30 秒 `busy_timeout` 与 WAL，每轮最多领取 100 条任务。

```
Client 进程                    共享数据库 / Hub                Server 进程
    │                              │                              │
    │ register(peer_id, service)   │   register(peer_id, service) │
    │ ───────────────────────────> │ <─────────────────────────── │
    │ peer.ready / peer.welcome    │                              │
    │ <────── 独立实例投递 ───────> │                              │
    │                              │                              │
    │ receive_message RPC          │                              │
    │ ───────────────────────────> │ ───── 原子领取 ────────────> │
    │                              │                       parser(msg)
    │ platform.* RPC               │                              │
    │ <─────────────────────────── │ <─────────────────────────── │
```

**核心类**（`core/queue/`）:

| 类 / 声明 | 文件 | 说明 |
| --- | --- | --- |
| `JobQueueBase` | `base.py` | 对称的 RPC 调用、结果关联、信号 fan-out、轮询和生命周期 |
| `JobQueueClient` | `client.py` | 平台进程的 RPC handler 与上下文解析 |
| `JobQueueServer` | `server.py` | Server 进程的 parser、事件、模块与查询 handler |
| `JobQueueBackend` | `backend.py` | 后端生命周期、配置选择及 Registry/Transport 装配 |
| `PeerIdentity` / `PeerRegistry` | `peer.py` | 唯一实例身份、状态和发现协议 |
| `DatabasePeerRegistry` | `database.py` | 数据库租约、状态、发现及实例失效事务 |
| `MessageTransport` | `transport.py` | 介质无关的请求、响应、批量投递和放弃等待协议 |
| `DatabaseMessageTransport` | `database.py` | 数据库任务投递、原子领取、回包与清理 |
| `WebSocketJobQueueBackend` | `websocket.py` | `httpx-ws` 客户端、ASGI Hub、实时路由、鉴权与背压控制 |
| `InMemoryJobQueueBackend` | `memory.py` | 后端契约测试基座（仅测试用） |
| `PeerSelector` | `peer.py` | 按实例、节点、角色、service、capability 筛选广播目标 |
| `ServiceRoute` | `peer.py` | 用 Rendezvous Hash 在同 service 的 ready 实例间稳定选路 |
| `RpcMethod` / `SignalMethod` | `rpc.py` | 强类型调用契约、编解码、绑定和信号声明 |

**RPC 与路由语义**：

- 接口在 `contracts.py` 用 `@remote()` 声明，在接收进程用 `.bind(JobQueueXxx)` 注册实现。直接 `await method(...)` 等待远端结果；`.submit(...)` 在后端接受投递后即返回。
- 多实例选路区分四种目标：service 字符串为竞争消费（anycast）；`peer_id` 为实例直投（如绑定了 `owner_peer_id` 的会话上下文操作）；`ServiceRoute(service, routing_key, role)` 为按业务键稳定分流（如无 owner 的主动会话）；`PeerSelector` 为逐实例广播（fan-out）。
- 广播用 `@signal()` 声明，通过 `.emit()`（仅等待投递）或 `.gather()`（汇总各目标结果与错误）调用：

```python
from core.queue.peer import PeerSelector
from core.queue.rpc import signal


@signal("cache.invalidate", timeout=30)
async def invalidate(version: int) -> None: ...


@invalidate.bind(JobQueueServer)
async def invalidate_local(version: int) -> None:
    ...


receipt = await invalidate.emit(PeerSelector.role("server"), version=8)
report = await invalidate.gather(PeerSelector.service("Server"), version=8)
```

**生命周期与后端细节**：

- **数据库后端**：任务行在消费或读取响应后即删除（`.submit()` / `.emit()` 由接收方删除，等待型 RPC 与 `.gather()` 由发起方 `consume_responses()` 读取后删除），遗留终态行由定时任务按 `(status, timestamp)` 索引清理。本地超时或取消时调用 `abandon()` 清理未处理的队列行（不会中断已开始执行的远端 handler）。
- **WebSocket 后端**：由 `jobqueue_websocket_mode = "embedded" | "external"` 与 `jobqueue_websocket_url` 配置。`embedded` 模式由 `bot.py` 自动启停 `jobqueue-hub` 子进程并要求回环 `ws` 地址；`external` 模式连接外部 Hub（非回环地址须用 `wss` 并配置共享令牌）。`pre_init` 会为留空的 `jobqueue_websocket_token` 生成 256 位随机密钥写回配置。Hub 校验握手身份、限制单 Peer 出站队列与帧大小，并在目标断线时将直投任务标记为 unavailable。
- **跨进程序列化**：进程间不共享内存对象，跨进程参数与返回值需可序列化（如 `MessageChain.to_list()`、`SessionInfo` 的 cattrs 序列化）。

---


---

### 12.1 导出系统（避免循环导入）

```python
# core/exports.py
class Exports(dict):
    def register(self, exporter: Type[T], name=None):
        self[exporter.__name__ if not name else name] = exporter

    def get(self, name, default: T = None) -> T:
        return self[name] if name in self else default


exports = Exports()
add_export = exports.register
```

```python
# 注册（在被导出对象定义处）
from core.exports import add_export
add_export(Bot)

# 使用（在会造成循环导入的地方）
from core.exports import exports
Bot = exports["Bot"]              # 或 exports.get("Bot") 拿可选值
```

注意 `exports.get()` 覆盖了 `dict.get` 的类型签名以便类型标注，行为一致（缺失返回 `default`）。取用要放在函数体里、而不是模块顶层，否则可能在注册之前就取到 `None`。


---

### 12.7 热重载

```python
ok, count = await ModulesManager.reload_module("module_name")
# 1. search_related_module() 找出同一 .py 里定义的全部模块
# 2. remove_modules() + 删除它们的 ModuleStatus 记录
# 3. reload_py_module()：从 sys.modules 摘除整个包后重新导入，得到全新命名空间
# 4. bulk_create 重建 ModuleStatus，refresh() 重建别名表，reload_db() 重挂模块数据库
```

`reload_py_module()` 失败时返回 `-999`（不是抛异常），所以调用方要判 `ok`。

reload 与 unload 都在 JobQueue 的非独占维护窗口内执行：窗口先停止领取新的队列任务并排空在途
handler，再进入 Scheduler 维护窗口。排空受限时抛 `QueueDrainTimeout`（`TimeoutError` 子类），
`reload_module()` / `unload_module()` 捕获后按失败返回，模块注册表与数据库状态保持原样。
正在等待维护锁的 handler 不计入排空范围：它们持有模块调用栈但处于暂停，只在本窗口结束后继续。

