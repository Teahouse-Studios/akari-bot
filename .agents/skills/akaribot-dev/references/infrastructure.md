# 加载、配置、数据库与队列

## 目录

- [模块加载系统](#55-模块加载系统-coreloaderpy)
- [组件注册系统](#56-组件注册系统-corecomponentpy)
- [配置系统](#57-配置系统-coreconfig)
- [数据库系统](#58-数据库系统-coredatabase)
- [队列系统](#59-队列系统-corequeue)
- [导出系统](#121-导出系统避免循环导入)
- [热重载](#127-热重载)

配置与数据库的模块侧调用示例位于 `module-development.md`，但两份文件都由主 `SKILL.md` 直接路由。涉及启动或跨进程生命周期时，再读取 `architecture.md`。

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

**单个模块加载失败不会中断整体流程**：异常被捕获后写进 `PrivateData.path / ".cache_loader"`（`core/loader.py:89`），`~module list` 等命令会读这个文件提示报错。所以模块写崩了不一定有明显报错，要去看这个缓存文件或日志。

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

基于 TOML 的配置系统，支持热重载。核心是 `CFGManager`（`core/config/__init__.py:48`）。

#### 配置项只在模板里声明，取值处直读类属性

**每个配置项有且只有一处定义，即配置模板类。** 取值处不重复书写键名、默认值、类型与表名：

```python
# 声明：bots/onebot/config.py
@on_bot_config("onebot")
class AiocqhttpConfig:
    qq_typing_emoji: int = 181

# 取值：bots/onebot/context.py —— 每次属性访问都走 CFGManager.get()，支持热重载
from bots.onebot.config import AiocqhttpConfig

qq_typing_emoji = str(AiocqhttpConfig.qq_typing_emoji)
```

模板类由 `ConfigMeta` 元类接管属性访问（`core/config/decorator.py`），读到的是**配置文件里的当前值**而非静态默认值；访问未声明的字段会抛 `AttributeError`，键名拼错当场暴露。

四个声明入口，全部集中在 `core/config/decorator.py`：

| 场景 | 写法 | 落在哪 | 模板类 |
|---|---|---|---|
| 表外顶层键 | `@on_base_config()` | `config.toml` 的表外顶层 | `BaseConfig` |
| 核心配置 | `@on_config("config")` / `@on_config("config", secret=True)` | `config.toml` 的 `[config]` / `[secret]` | `CoreConfig` |
| 独立核心配置 | `@on_config("jobqueue")` / `@on_config("jobqueue", secret=True)` | `jobqueue.toml` 的 `[jobqueue]` / `[jobqueue_secret]` | `JobQueueConfig` |
| 平台配置 | `@on_bot_config("onebot")` / `@on_bot_config("onebot", secret=True)` | `[bot_onebot]` / `[bot_onebot_secret]` | `AiocqhttpConfig` 等 |
| 模块配置 | `@on_module_config("dice")` / `@on_module_config("dice", secret=True)` | `[module_dice]` / `[module_dice_secret]` | `DiceConfig` 等 |

`on_config()` 是底层入口，只有核心配置直接用它；平台与模块各有专用装饰器把表名前缀固定住，不必再手写 `table_type`。传入的名称都有约束，`tests/unit/test_config_template.py` 会逐条校验：

- `on_bot_config("<平台名>")` 的平台名须与 `bots/` 下的**目录名**一致——守护进程正是以 `bot_<目录名>` 的表名去查找该平台的 `enable` 配置的，对不上该平台会被判定为禁用。
- `on_module_config("<模块名>")` 的模块名通常须与包内 `module()` 声明的一致。模块主名为连字符、下划线形式作为命令别名保留时，配置表名可沿用下划线形式。

模块配置**必须**用 `on_module_config`，不要用 `Bind.Module.config()`：后者要求模板反向导入模块对象（`from . import dice`），同包内任何文件在顶层读取该模板都会与包的初始化互相等待而形成循环导入。`on_module_config` 不依赖模块对象，模板因而是叶子模块。

核心模板按职责分布在 `core/config/`：表外元数据位于 `base.py`，通用核心项位于 `core.py`，JobQueue、
S3 与 WebRender 分别位于 `jobqueue.py`、`s3.py` 和 `webrender.py`。`JobQueueConfig` 与
`JobQueueSecretConfig` 读取独立 `jobqueue.toml` 的 `[jobqueue]` 与 `[jobqueue_secret]`；S3 和 WebRender
同样分别使用各自的 TOML 文件。`base.py` 另有若干类名的兼容重导出；新增调用应直接从所属领域模块导入，
避免形成单一配置入口。

`default_locale`、`config_version` 这类位于 `config.toml` 中任何表之外的键归 `BaseConfig` 管（`core/config/base.py`）。它们由 `core/scripts/config_generate.py` 在建立配置文件时写入、由 `core/config/update.py` 的版本迁移维护，模板声明只是提供一个带类型的读取入口：

```python
from core.config.base import BaseConfig

default_locale = BaseConfig.default_locale
```

不要改用 `@on_config("config")` 声明它们——那会把键挪进 `[config]` 表内，改变配置文件结构。

#### 配置的生成只发生在 pre_init

`bot.py` 的 `pre_init()` 会调用 `core.config.scan.scan_config_templates()` 导入全部配置模板、补全缺失的键，任一模板加载失败即中止启动。此后守护进程置位环境变量 `AKARI_CONFIG_READONLY=1` 再 spawn 子进程，**bot 与 server 子进程一律只读**：

| 方法 | 只读进程中的行为 |
|---|---|
| `CFGManager.write()` / `delete()` / `save()` | 抛 `ConfigOperationError` |
| `CFGManager.get()` 读到缺失的键 | 经 `write()` 回写默认值时抛错；无默认值时返回 `None` 不抛 |
| `CFGManager.load()` / `watch()` | 正常，热重载不受影响 |
| 配置模板导入 | `__config_fields__` 照常登记，不补写配置文件 |

之所以要这道闸门：`multiprocessing` 以 spawn / forkserver 启动子进程时会把主模块以 `__mp_main__` 重新导入一遍，每个子进程都会再跑一次 `bot.py` 顶层的模板导入；`core/config/update.py` 的版本迁移又是导入期执行的。不隔离的话同一批配置项会被多个进程反复补写。

因此**新增配置项后必须重启机器人**，否则子进程读到该键时会抛 `ConfigOperationError`——这是刻意的，用来把「模板漏声明」当场暴露出来，而不是静默退化成默认值。

需要在运行期写配置的只有交互式编辑命令与启动期的共享身份、密钥自举两类，一律走授权接口：

```python
CFGManager.edit_write("jwt_secret", value, secret=True, table_name="bot_web")
CFGManager.edit_delete("some_key", "module_wiki")
```

`tests/unit/test_config_template.py` 会断言 `core/config/` 与 `core/scripts/` 之外不存在直接调用 `CFGManager.write` / `delete` / `save` 的地方。

#### Config() 门面函数

`Config()` 仅保留给**键名在运行时才确定**的场景。目前生产代码里已无任何 `Config()` 调用，全部配置项都经模板类属性读取；新增调用前先确认真的无法用模板表达。这类调用不得带 `default` 或 `table_name` 参数，否则 `tests/unit/test_config_template.py` 会拦下。

```python
def Config(
    q: str,                              # 配置项键名
    default: Any | None = None,          # 默认值（读不到时写回配置文件）
    cfg_type: type | tuple | None = None, # 类型约束
    secret: bool = False,                # 是否写入 *_secret 表
    table_name: str | None = None,       # 配置表名，模块用 "module_<name>"
    get_url: bool = False,               # 按 URL 处理（补全协议头与尾部斜杠）
    _global: bool = False,               # 内部用：跨所有表查找
    _generate: bool = False,             # 内部用：仅生成不读取
) -> Any
```

需要对模板取到的地址做 URL 补全时，用 `core.config.format_url()`，不要另写一遍正则：

```python
from core.config import format_url
from core.config.webrender import WebRenderConfig

remote_web_render_url = format_url(WebRenderConfig.remote_web_render_url)
```

#### 配置注释规范

**在模板中新增字段时，必须在对应的 locale 文件中添加注释说明。** 键名格式为：

```
config.comments.<config表名>.<config字段名>
```

注释所在的文件按模板归属：核心配置写 `core/locales/zh_cn.json`，平台配置写 `bots/<平台>/locales/zh_cn.json`，模块配置写 `modules/<模块>/locales/zh_cn.json`。

示例：

```json
{
    "config.comments.config.typo_check_module_score": "模块拼写检查容许相似度，范围 0 到 1 之间。",
    "config.comments.bot_telegram.enable": "是否开启 Telegram 客户端。"
}
```

- `@on_config("config")` → `config.comments.config.<字段名>`
- `@on_config("config", secret=True)` → `config.comments.secret.<字段名>`
- `@on_base_config()` → `config.comments.<字段名>`（表外顶层键，没有表名这一层）
- `@on_bot_config("<平台>")` → `config.comments.bot_<平台>.<字段名>`，`secret=True` 时为 `config.comments.bot_<平台>_secret.<字段名>`
- `@on_module_config("<模块>")` → `config.comments.module_<模块>.<字段名>`，`secret=True` 时为 `config.comments.module_<模块>_secret.<字段名>`

当字段需要说明多个选项的差异、限制或故障边界，行尾注释不足以清晰表达时，可通过
`standalone_comments` 在字段前生成多行独立注释块。映射键必须是同一模板中已声明的字段名，值必须是
按展示顺序排列的非空 i18n 键元组；字段名或参数形式无效时，模板导入会明确失败。找不到翻译的说明行会
被跳过，不会将原始 i18n 键写入 TOML：

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

独立注释文本仍存放在模板所属的 `zh_cn.json` 中。普通字段说明继续使用
`config.comments.<配置表名>.<字段名>`；独立说明建议使用 `config.notes.<领域>.<主题>.<说明行>`，以免与
行尾注释混淆。

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

两个数据层模型都继承抽象基类 `UnionInfo`，两个映射层模型都继承 `UnionBind`；
共用的解析、展开逻辑写在基类上，子类只声明自己的字段与 `union_scope` / `bind_model`。
**映射层只回答「这个平台 ID 属于哪个 union」，不承载任何状态**——状态若下放到单个 ID，
换用组内另一个 ID 即可绕过。

- `StoredData` - 通用键值存储
- `AnalyticsData` - 命令使用统计（同时记原始 ID 与 union ID）
- `ModuleStatus` - 模块加载状态
- `DBVersion` - 数据库版本
- `UnfriendlyActionRecords` - 违规记录（同时记原始 ID 与 union ID）
- `JobQueuesTable` - 任务队列表（数据库后端的跨进程投递载体）
- `JobQueuePeersTable` - JobQueue Peer 注册表（数据库后端的 Registry）
- `MaliciousLoginRecords` - WebUI 恶意登录记录

**union 解析的唯一入口是 `UnionInfo.resolve_union(平台 ID, create=True)`**：它查映射表拿到 union，
取出数据行，并把映射行挂到实例的 `.bind` 上。`get_by_target_id()` / `get_by_sender_id()`
是它的会话友好包装（多接受 `MessageSession`），模块表继承 `DBModel` 拿到的同名方法则是
「先解析 union，再按 union 取本表的行」。

两个必须记住的约定：

- **封禁只有 `UnionInfo.blocked` 一个字段，不存在「某个 ID 单独被封」这回事。** union 下的全部平台 ID
  共享同一行，所以封禁天然对组内所有 ID 生效，映射表上不需要、也不该再放一份标记。
  封了之后也洗不白：能改变 ID 所属 union 的路径只有 `merge_union`（`blocked` 取并集，只会把封禁
  传染给对方）、`unbind_id`（新组继承 `self.blocked`，且映射行是**改挂**不是删建，任何时刻都不会
  出现「没有映射行」的中间态）和 `bind_id`（已有映射行的 ID 直接拒绝迁组）。`resolve_union()` 只为
  从未见过的 ID 建新组，有映射行的永远解析回原组。
- **模块表若以 `union_id` 为键，必须声明 `union_scope`**（`UNION_SCOPE_SENDER` / `UNION_SCOPE_TARGET`）。
  未声明的表会被 `iter_union_models()` 跳过并告警，即不参与 union 合并与映射补建——
  因为无从判断它存的是账号数据还是场景数据，两个域都处理会把二者互相搬走。

**模块数据库**: 模块可以在 `database/models.py` 中定义自己的模型，`init_db()` 通过 `fetch_module_db()` 自动发现并注册到 `default` 连接。

**任务队列表的升级约束**：`core/database/update.py` 的 `db_version < 5` 分支不保留既有任务记录，而是执行
`DROP TABLE IF EXISTS job_queues`，随后通过 `Tortoise.generate_schemas(safe=True)` 按当前模型重建该表。
JobQueue 记录属于临时在途数据，升级不予保留；执行迁移前必须停止全部 Bot 与 Server 进程。

### 5.9 队列系统 (`core/queue/`)

可配置后端支撑的 Peer RPC 与信号总线，用于 Client、Server 以及未来其它 Worker 进程之间的异步通信。
`jobqueue.toml` 中的 `[jobqueue].jobqueue_backend` 选择一套完整的 `JobQueueBackend`，其 `PeerRegistry` 与 `MessageTransport`
不得跨后端组合。生产实现包括 `database` 和 `websocket`；未知值、WebSocket 连接失败或鉴权失败时须明确
终止初始化，不得自动回退。进程内 `Alive` 只作为同步查询缓存，不得作为在线凭据。
代码通过 `core.config.jobqueue.JobQueueConfig` 与 `JobQueueSecretConfig` 读取这些配置；JobQueue 字段
不并入通用 `CoreConfig`。
新生成的配置默认使用 `websocket`，该后端亦是项目推荐选项。已有 `database` 配置不会被自动改写；
当主数据库为 SQLite 时，守护进程会在启动阶段输出非阻断警告。SQLite 连接默认先设置 30 秒
`busy_timeout` 再启用 WAL，数据库传输每轮最多领取 100 条任务；这些措施只减少锁冲突，不改变 SQLite
的单写者边界。

```
Client 进程                    共享数据库                     Server 进程
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
| `JobQueueBackend` | `backend.py` | 后端生命周期、配置选择及 Registry/Transport 整套装配 |
| `PeerIdentity` / `PeerRegistry` | `peer.py` | 唯一实例身份、状态和权威发现协议 |
| `DatabasePeerRegistry` | `database.py` | 数据库租约、状态、发现及实例失效事务 |
| `MessageTransport` | `transport.py` | 介质无关的请求、响应、批量投递和放弃等待协议 |
| `DatabaseMessageTransport` | `database.py` | 数据库任务投递、原子领取、回包与及时清理 |
| `WebSocketJobQueueBackend` | `websocket.py` | `httpx-ws` 客户端、ASGI Hub、实时路由、鉴权与背压控制 |
| `InMemoryJobQueueBackend` | `memory.py` | 不依赖 ORM 的后端契约测试基座，不属于生产配置选项 |
| `PeerSelector` | `peer.py` | 按实例、节点、角色、service、capability 筛选广播目标 |
| `ServiceRoute` | `peer.py` | 用 Rendezvous Hash 在同 service 的 ready 实例间稳定选路 |
| `RpcMethod` / `SignalMethod` | `rpc.py` | 强类型调用契约、编解码、绑定和信号声明 |

普通接口在 `contracts.py` 用 `@remote()` 声明，在接收进程用 `.bind(JobQueueXxx)` 注册实现。
直接 `await method(...)` 等待远端结果；`.submit(...)` 只等待当前后端接受投递，不保证最终执行成功。
会话绑定的平台操作优先使用 `owner_peer_id` 回到最初接收消息的 Client；主动会话没有 owner 时，
使用 `ServiceRoute(service, routing_key, role)` 选择一个稳定实例。

每个进程启动时生成唯一 `peer_id`，以 `role / service / node_id / capabilities / metadata` 注册，
并经历 `starting → ready → maintenance/draining → stopped`。运行中续租，异常退出由租约过期识别。
正常启动的 `pre_init` 会在 spawn 任何子进程前检查 `[jobqueue].jobqueue_node_id`；该值缺失、为占位符或
仅含空白时，生成 UUID 并写回配置。共用同一配置目录的进程因而共享稳定的部署节点标签，进程级唯一性仍由
`peer_id` 提供。`configure_peer()` 显式参数可覆盖配置；绕过守护进程的入口在配置为空时仍以进程级 UUID
防御性回退。不得从计算机名或其它宿主机信息推导节点标识。配置变更须在相关进程重启后才会反映到 Registry。
`peer.ready` 与定向 `peer.welcome` 让新旧进程互相辨认；实际在线判断仍以 Registry 为准，信号只负责
降低拓扑变化的传播延迟。

JobQueue 层面的广播用 `@signal()` 声明。发送端先用 `PeerSelector` 快照所有 ready 实例，再为每个
目标创建独立逻辑投递；数据库后端为每个目标建立独立队列行。这些投递共享 `correlation_id`，但有各自的
`task_id / ACK / error`，数据库行还分别记录 `claimed_by`。
因此一个目标失败不会吞掉或覆盖其它目标的结果：

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

队列行仅承担投递和回包，不作为审计记录长期保存。`.submit()` / `.emit()` 创建的任务将
`expects_response` 设为 False，处理完成后由接收方直接删除；普通等待型 RPC 与 `.gather()` 的结果由
发起方通过 `consume_responses()` 读取后删除。调用方异常退出所遗留的终态行由定时任务兜底清理，
`(status, timestamp)` 复合索引用于避免清理查询退化为全表扫描。
等待型调用在本地取消或超时后通过 `abandon()` 要求后端尽力清理；数据库后端会删除仍存在的相应队列行。
该操作不会取消已经开始的远端处理器，也不得据此推断外部副作用未发生或可以安全重试。

批量投递返回逐任务的 `accepted / rejected / unknown`。`SignalReceipt.deliveries` 只包含后端明确接受的目标，
拒绝原因和接受状态未知的 Peer 分别位于 `errors` 与 `unknown`。接收端通过
`respond(request, response)` 回包，原请求为 WebSocket 等无状态响应帧提供来源路由上下文。
新增生产后端前，先使用共享 `InMemoryBroker` 的 `InMemoryJobQueueBackend` 运行相同的双向 RPC、信号 fan-out
和 Peer 失效测试，以确认 Runtime 没有重新依赖 ORM；不得将 `memory` 暴露为用户配置值。

WebSocket 后端使用独立 Hub 同时承担 Registry 与 Transport。内置模式由 `bot.py` 在 Bot 和 Server 之前
启动 `jobqueue-hub` 子进程，关闭顺序则相反；外部模式只连接配置的 Hub URL。配置以
`jobqueue_websocket_mode = "embedded" | "external"` 明确部署模式，不根据 URL 主机推断；
`jobqueue_websocket_url` 是唯一地址来源。内置模式从 URL 同时解析监听主机、端口和路径，并要求使用回环
`ws` 地址；外部模式将 URL 仅作为 Peer 连接地址，非回环连接必须使用 `wss` 并配置共享令牌。需要区分
监听地址与公开连接地址的多节点或反向代理部署应使用外部模式，不得重新增加重复的 bind host/port 配置。
`pre_init` 会为缺失、占位或空白的 `jobqueue_websocket_token` 生成 256 位安全随机密钥并写回密钥表，确保
随后启动的 Hub、Bot 和 Server 读取同一值。此自举只协调共用同一配置目录的进程；外部 Hub 和多配置目录
部署必须显式分发同一密钥，清空字段会在下次正常启动时触发密钥轮换。
Hub 以握手身份覆盖请求自报的 `source_peer_id`，拒绝重复 Peer、越权状态修改和非目标回包。每个 Peer 的
出站队列和协议帧大小均有上限，队列满时明确拒绝新投递；控制命令超时按 unknown 处理。Hub 不持久化离线
任务或在途结果，目标断线后将直投任务终结为 unavailable，且不得重新分配可能已经执行的副作用请求。
超过 deadline 的请求关联状态应及时释放，并向仍在线的来源返回 timeout；该清理不表示已经开始的远端
副作用被撤销。

多实例语义必须区分：service 字符串是竞争消费的 anycast；`peer_id` 是实例直投；`ServiceRoute` 是
按业务键稳定分流；`PeerSelector` 是逐实例 fan-out。不要用一条 service 队列记录模拟广播，否则只会
被一个实例领取。

当前 JobQueue 已预留同类型多 Client / Server 的发现、分流、回源、摘流和广播能力，但真正开启多
Server 还需要 Scheduler leader election、模块热重载的共享 epoch、Server 内存会话故障策略及
副作用幂等。模块热重载不能直接在当前 Queue handler 内同步广播到所有 Server：目标实例进入维护
窗口时可能等待发起 handler，而发起 handler又等待广播 ACK，形成分布式死锁。跨实例控制操作应由
稳定协调者或独立控制面发起。

同账号多 Client 的平台 SDK 入口还需适配器层实现分片、租约或事件去重；JobQueue 只能分流已经进入
系统的任务。广播是发送时的在线实例快照，不负责向离线实例重放；必须补齐的状态应持久化 version / epoch，
实例启动后主动对账。

> **注意**：因为是数据库轮询而不是共享内存，两个进程之间**不共享任何 Python 对象**。要跨进程传的东西必须能序列化（`MessageChain.to_list()` / `SessionInfo` 的 cattrs 序列化就是为此）。

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
# 3. reload_py_module()：先递归 reload 所有子模块，再 importlib.reload() 自身
# 4. bulk_create 重建 ModuleStatus，refresh() 重建别名表，reload_db() 重挂模块数据库
```

`reload_py_module()` 失败时返回 `-999`（不是抛异常），所以调用方要判 `ok`。

