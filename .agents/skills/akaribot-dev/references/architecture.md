# 架构、启动与消息链路

## 目录

- [项目速览](#1-项目速览)
- [技术栈与依赖](#2-技术栈与依赖)
- [架构总览](#3-架构总览)
- [启动流程详解](#4-启动流程详解)
- [消息处理全链路](#6-消息处理全链路)
- [目录结构参考](#13-目录结构参考)

---

## 1. 项目速览

**AkariBot（小可）** 是一个多平台、可扩展的异步聊天机器人框架。

- **语言**: Python 3.12+
- **异步框架**: asyncio
- **ORM**: Tortoise ORM（支持 SQLite/MySQL）
- **Web 框架**: FastAPI（用于 Webhook 和 API）
- **调度器**: APScheduler
- **许可证**: AGPL-3.0

### 支持平台

| 平台         | 适配器目录       | 协议/SDK              |
| ------------ | ---------------- | --------------------- |
| QQ（第三方） | `bots/onebot/`   | OneBot 11 (aiocqhttp) |
| QQ（Milky）  | `bots/milky/`    | Milky (milky-python-sdk) |
| QQ（官方）   | `bots/qqbot/`    | QQ Bot API (qq-botpy-sdk) |
| Discord      | `bots/discord/`  | py-cord               |
| Telegram     | `bots/telegram/` | aiogram               |
| KOOK         | `bots/kook/`     | khl-py                |
| Matrix       | `bots/matrix/`   | matrix-nio            |
| Web          | `bots/web/`      | FastAPI               |

`bots/onebot/` 与 `bots/milky/` 的 `client_name` 都是 `QQ`，是同一平台的两套协议实现。

---

## 2. 技术栈与依赖

### 包管理

使用 **uv** 管理依赖：

```bash
uv sync                    # 安装依赖
uv add <package>           # 添加新依赖
uv lock                    # 锁定依赖
```

依赖在 `pyproject.toml` 中按功能分组管理，新增依赖需移至对应注释分组下并按字母排序。

### 核心依赖

| 类别   | 包名                     | 用途                       |
| ------ | ------------------------ | -------------------------- |
| 配置   | `tomlkit`                | TOML 配置解析（保留注释）  |
| 数据库 | `tortoise-orm[asyncmy]`  | ORM（SQLite / MySQL）      |
| HTTP   | `httpx`, `httpx-ws`, `aiofile` | 异步 HTTP、WebSocket 客户端与文件 |
| 日志   | `loguru`                 | 结构化日志                 |
| 调度   | `APScheduler`            | 定时任务                   |
| Web    | `fastapi`, `uvicorn`     | Web 服务器                 |
| 序列化 | `orjson`                 | 高性能 JSON                |
| 属性   | `attrs`, `cattrs`        | 数据类 / 结构化序列化      |
| 工具   | `rapidfuzz`              | 模糊匹配（错字纠正）       |
| 工具   | `tenacity`               | 重试机制                   |
| 测试   | `coverage`               | 代码覆盖率                 |
| 代码   | `ruff`（dev 组）         | 格式化 + 静态检查          |

**第一方服务依赖**（Teahouse 自家发布的包，升级时留意版本约束是精确 `==`）：

| 包名                | 用途                     |
| ------------------- | ------------------------ |
| `akari-bot-i18n`    | i18n 语言包              |
| `akari-bot-webrender` | 网页渲染服务           |
| `akari-bot-webui`   | Web 控制台前端           |

平台 SDK：`aiocqhttp`(OneBot) / `milky-python-sdk`(Milky) / `qq-botpy-sdk`(QQ 官方) / `py-cord`(Discord) / `aiogram`(Telegram) / `khl-py`(KOOK) / `matrix-nio`(Matrix)。

---

## 3. 架构总览

### 进程模型

```
bot.py (守护进程)
    │
    ├── WebSocket JobQueue Hub（选择内置 WebSocket 后端时）
    │   └── 独立控制面与实时路由进程
    │
    ├── Bot 进程 1 (e.g., onebot)
    │   └── 接收平台消息 → 通过 JobQueue 发送到 Server
    │
    ├── Bot 进程 2 (e.g., discord)
    │   └── 接收平台消息 → 通过 JobQueue 发送到 Server
    │
    ├── ...
    │
    └── Server 进程
        ├── JobQueueServer: 处理消息队列
        ├── 模块系统: 加载/执行命令模块
        ├── 调度器: APScheduler 定时任务
        └── FastAPI: Webhook / API
```

**关键设计**: Bot 进程和 Server 进程通过可配置的 **Peer RPC 与信号总线**通信。完整后端可选择数据库，
也可选择由独立 Hub 提供的 WebSocket 实时传输；两种后端不得交叉组合或自动回退。Bot 进程负责平台 SDK
交互，Server 进程负责命令解析和业务逻辑。每个进程实例有独立 `peer_id`，同类实例共享稳定 `service`；
Registry 租约负责发现，service anycast / 稳定路由负责分流，逐实例 signal 负责广播。

### 核心分层

```
┌─────────────────────────────────────────────┐
│              平台适配器 (bots/)               │
│  onebot/ discord/ telegram/ kook/ matrix/   │
├─────────────────────────────────────────────┤
│            Bot 核心框架 (core/)              │
│  ┌─────────┐ ┌────────┐ ┌──────────────┐   │
│  │  Bot    │ │Session │ │   Parser     │   │
│  │  Class  │ │ System │ │ (命令解析)    │   │
│  └────┬────┘ └───┬────┘ └──────┬───────┘   │
│       │          │             │            │
│  ┌────┴──────────┴─────────────┴────────┐   │
│  │          MessageChain (消息链)        │   │
│  └──────────────────────────────────────┘   │
│  ┌─────────┐ ┌──────────┐ ┌───────────┐    │
│  │ Config  │ │ Database │ │   Queue   │    │
│  │ (TOML)  │ │ (Tortoise)│ │ (JobQueue)│   │
│  └─────────┘ └──────────┘ └───────────┘    │
├─────────────────────────────────────────────┤
│           命令模块 (modules/)                │
│  core/ wiki/ arcaea/ maimai/ dice/ ...      │
└─────────────────────────────────────────────┘
```

---

## 4. 启动流程详解

### `bot.py` 入口

```python
# bot.py:463 - main() 是同步函数，每轮用 asyncio.run() 起一个全新事件循环
def main():
    base_import_lists = list(sys.modules)  # 记录基线，重启时只清理增量模块

    while True:
        try:
            asyncio.run(main_async())
        except RestartBot:
            clear_import_cache()  # 删除 base_import_lists 之外的所有 sys.modules 条目
            continue  # 热重启支持
        except (KeyboardInterrupt, SystemExit):
            break
```

`__main__` 块里还有**单实例文件锁**：在仓库根写 `.bot.lock`，Windows 用 `msvcrt.locking`、其他平台用 `fcntl.flock`，抢锁失败直接 `sys.exit(1)`。所以同一仓库目录下不能同时跑两个 `bot.py`。

### 启动序列

1. **`pre_init()`** (`bot.py:112`)，注意它是在一个**独立子进程**里跑完就退出的（`multiprocess_run_until_complete`）：
    - `shutil.rmtree(cache_path)` 直接删除整个缓存目录后重建
    - 扫描配置模板；为留空的 JobQueue `node_id` 与 WebSocket token 生成随机值并原子写回配置
    - 初始化 Tortoise ORM 数据库连接
    - 执行数据库迁移（`DBVersion` 检查：无记录 → `convert_database()`；版本落后 → `update_database()`）
    - 设置超级用户（从配置读取 `base_superuser`）

2. **`run_bot()`** (`bot.py:262`):
    - 扫描 `bots/` 目录获取所有适配器
    - 检查 `config/bot_<平台>.toml` 中对应 `[bot_<平台>].enable` 配置
    - 为每个启用的 bot 创建 **子进程**: `multiprocessing.Process(target=go, args=(bot_name,))`
    - 创建 Server 子进程: `multiprocessing.Process(target=server_run_async)`
    - 进入监控循环：检查进程状态，失败自动重启（最多 3 次）

3. **Bot 子进程启动** (`bots/{platform}/bot.py`):
    - 调用 `Bot.register_bot(client_name)` 注册客户端
    - 调用 `Bot.register_context_manager(ContextManager)` 注册上下文管理器
    - 启动平台 SDK 监听消息
    - 收到消息时调用 `Bot.process_message(session_info, ctx)`

4. **Server 进程启动** (`core/server/run.py` 调用 `core/server/init.py`):
    - 初始化数据库
    - 加载所有模块 (`load_modules()`)
    - 注册模块中的定时任务到 APScheduler
    - 启动调度器
    - 启动 JobQueueServer 轮询

### JobQueue Peer 启动与发现

Client 和 Server 在开始接收业务任务前都执行同一套屏障：

1. 生成本次进程生命周期唯一的 `peer_id`，登记 `role / service / node_id / capabilities / metadata`；其中
   `node_id` 依次取自 `configure_peer()` 显式参数和 `jobqueue.toml` 的 `[jobqueue].jobqueue_node_id`。正常启动
   已由 `pre_init` 为留空值生成 UUID 并写回，因此共用配置目录的进程共享稳定的部署节点标签；绕过守护进程
   的入口仅在配置仍为空时生成进程级临时 UUID。节点标识不得读取或推导计算机名；
2. 启动由 `[jobqueue].jobqueue_backend` 选择的完整后端，再以 `starting` 向其权威 Registry 注册，初始化完成后
   切换为 `ready`；数据库后端写入 `JobQueuePeersTable`，WebSocket 后端通过已鉴权连接向独立 Hub 注册；
3. 查询 Registry 获得当前拓扑，并向其它 ready 实例逐个投递 `peer.ready`；
4. 已在线实例用定向 `peer.welcome` 回应，新旧双方由此快速更新本地缓存；
5. 每 15 秒续租、每 10 秒完整对账；异常退出最多约 45 秒后由租约过期识别。

`peer.ready/welcome` 是变化通知，不是在线事实本身。接收端会重新读取 Registry，并校验信号来源
`source_peer_id` 与载荷中的 `peer_id` 一致。维护、恢复、摘流和停止信号同样必须与 Registry 当前状态
一致，迟到信号不能覆盖更新的状态。

同一 `service` 下可以登记多个同类型实例：普通 service 目标由它们竞争领取；要求场景粘性的消息使用
Rendezvous Hash 选择实例；广播先快照目标，再生成逐实例投递记录。因此未来扩大 Client / Server 数量
不需要改变业务 RPC 载荷。

### 退出码约定

| 退出码 | bot 子进程           | server 子进程            |
| ------ | -------------------- | ------------------------ |
| 0      | 正常退出（不重启）   | 整个守护进程 `sys.exit(0)` |
| 33     | 重启所有 bot 进程    | 重启所有 bot 进程        |
| 78     | 明确无需重启，摘掉该进程 | 同左（按其他码处理前先判 78） |
| 其他   | 错误（重启当前 bot） | 守护进程带该码退出       |

`jobqueue-hub` 子进程不参与重启：它一旦退出，守护进程直接带该码 `sys.exit`。

重启不是无限的：`restart_bot_process()` 用 `failed_to_start_attempts` 记账，**同一 bot 在 60 秒窗口内失败 3 次就放弃重启**（窗口过期会重新计数）。

---


---

## 6. 消息处理全链路

### 接收消息流程

```
1. 平台 SDK 收到消息
       ↓
2. bots/{platform}/bot.py - message_handler()
   - 解析平台消息格式
   - 创建 SessionInfo（含 target_id, sender_id 等）
       ↓
3. Bot.process_message(session_info, ctx)
   - 从 ContextSlots 获取平台 ContextManager
   - 注入平台 Features
   - 添加上下文到 ContextManager
       ↓
4. ServerAPI.receive_message(session_info)
   - 序列化 SessionInfo 为 JSON
   - 按场景路由键从 ready Server 中稳定选择一个实例
   - 写入 JobQueuesTable；尚无 Server 时保留为 service anycast 任务
       ↓
5. JobQueueServer.check_job_queue() (Server 进程)
   - 轮询 JobQueuesTable
   - 反序列化 SessionInfo
   - 创建 MessageSession
       ↓
6. parser(msg)
   - 权限检查
   - 前缀匹配
   - 命令解析
   - 模块匹配
       ↓
7. 执行模块函数
   - msg.send_message() → PlatformAPI.send_message()
   - msg.finish() → 发送并抛出 SessionFinished
       ↓
8. 通过 JobQueue 返回到 Bot 进程
       ↓
9. ContextManager.send_message() → 平台 SDK 发送
```

### 主动推送流程

```
定时任务/钩子触发
       ↓
Bot.post_message(module_name, message, session_list)
   - 从数据库查询启用了该模块的目标列表
   - group_sessions_by_channel(): 按「场景组 + 消息通道」归拢，同一通道只推一次
   - 只发队首，session_info.next_hops = 该通道内其余会话的 target_id
       ↓
PlatformAPI.post_message.submit(session_info, message, module_name)
       ↓ (跨进程)
JobQueueClient 的 platform.post_message handler → ContextManager.send_message(quote=False)
       ↓
   拿到 msgid → 结束，这条通道已送达
   拿不到    → ServerAPI.post_next_hop.submit(next_hops, message, module_name)
                   ↓ (跨进程，回到服务端——下一跳可能是另一个平台，只有服务端解析得了)
              Server handler → fetch_target() → 再来一轮
```

跳表每次只会变短，不会成环。因此 `*FetchedContextManager` 的 `send_message` **必须返回真实的消息 ID**：
onebot / qqbot 的主动消息要按冷却排队，队列里放的是 `(future, 任务参数)`，
`send_message` 等 future，`process_tasks()` 发完再 `set_result` —— 冷却节奏不变，但调用方拿得到结果。

### 私信发送流程

```
msg.send_private_message(message, user_id)
   - session_info.support_private_msg 为 False 时直接返回 []，不走队列
       ↓
PlatformAPI.send_private_msg(session_info, user_id, message)
       ↓ (跨进程；wait=True 才拿得到消息 ID)
ContextManager.send_private_msg(session_info, user_id, message)
   - derive_private_session() 把场景换成私聊，再复用自家 send_message
       ↓
平台 SDK 发送消息 → 消息 ID 列表（空列表 = 发送失败）
```

入站会话记录 `owner_peer_id`，需要访问原始平台 SDK 上下文的删除消息、反应、hold/release 等操作会
直投该 Client 实例。Server 创建的主动会话不绑定 owner，按场景键在同 service 的 ready Client 中
稳定分流。实例进入 `maintenance` 或 `draining` 后立即退出新路由，正常停止或租约过期会将发往该
实例的未完成直投任务终结为 unavailable。

### JobQueue 信号广播与多实例边界

JobQueue 信号不是对外发送的聊天消息，也不是一条供多个消费者竞争的共享记录。发送端使用
`PeerSelector` 按 `peer_id / node_id / role / service / capability` 选择目标，并为每个 ready 实例创建
独立逻辑投递；数据库后端会为每个目标创建单独队列行。所有投递共享一个 `correlation_id`，每个目标分别
领取、执行和 ACK；批量发送逐项区分后端明确接受、拒绝和接受状态未知的目标，可选择只取得投递结果，
或汇总所有目标的执行结果与错误。

广播是在线实例快照，不提供离线重放。配置、模块版本等必须最终一致的状态应持久化 version / epoch，
进程启动后对账，信号只用于加速刷新。

JobQueue 层已为同类型多 Client / Server 预留实例发现、anycast、稳定分流、回源和摘流；外围仍需：

- Scheduler leader election 或分布式去重，避免每个 Server 重复执行单例任务；
- 模块加载和热重载的集群 epoch 与独立协调者，避免 Queue handler 等待广播 ACK 时形成维护死锁；
- Server 进程内会话和临时状态的故障迁移或明确失效策略；
- 同平台账号多 Client 的 SDK 入口分片、主备租约或重复事件去重；
- 生产环境使用适合多进程竞争的数据库，并为有副作用的 handler 设计幂等键。

---


---

## 13. 目录结构参考

```
akari-bot/
├── bot.py                    # 入口点
├── conftest.py               # pytest 适配层的根级 conftest
├── pyproject.toml            # 项目配置和依赖
├── requirements.txt          # 导出的依赖列表
├── uv.lock                   # 依赖锁文件
│
├── core/                     # 核心框架
│   ├── builtins/
│   │   ├── bot/              # Bot 类
│   │   ├── message/          # 消息系统
│   │   │   ├── chain.py      # MessageChain / I18NMessageChain / PlatformMessageChain
│   │   │   ├── elements.py   # 消息元素类（XxxElement）
│   │   │   └── internal.py   # 便捷别名（.assign 工厂）
│   │   ├── session/          # 会话系统
│   │   │   ├── context.py    # ContextManager
│   │   │   ├── features.py   # Features
│   │   │   ├── info.py       # SessionInfo / FetchedSessionInfo / EventInfo
│   │   │   ├── internal.py   # MessageSession / FinishedSession
│   │   │   ├── bot_state.py  # BotState
│   │   │   ├── event_types.py
│   │   │   ├── lock.py       # ExecutionLockList
│   │   │   └── tasks.py      # SessionTaskManager
│   │   ├── parser/           # 命令解析
│   │   │   ├── args.py       # 模板解析
│   │   │   ├── command.py    # CommandParser
│   │   │   ├── message.py    # parser() 主函数
│   │   │   └── hooks/        # parser 入口 hook（点位、分发、结果类型）
│   │   ├── hooks/            # 具名模块 hook 的分发与执行
│   │   ├── filter/           # 出站内容过滤
│   │   ├── converter/        # cattrs 序列化钩子
│   │   ├── temp/             # 运行时临时数据（Temp）
│   │   ├── types/            # 内置类型
│   │   └── utils/            # 内置工具
│   ├── component.py          # module() 注册函数
│   ├── loader.py             # ModulesManager
│   ├── module_runtime.py     # 模块 runtime generation 管理
│   ├── types/                # Module / Command / Message 类型定义
│   ├── constants/            # 路径、版本、默认值、异常
│   ├── config/               # 配置系统（模板装饰器 + CFGManager）
│   ├── database/             # 数据库系统（models.py / local.py / base.py）
│   ├── queue/                # JobQueue：Peer RPC、信号总线、可切后端
│   ├── server/               # Server 进程入口与生命周期
│   ├── client/               # 客户端侧公共逻辑
│   ├── tester/               # 测试框架（含 mock/ 与 pytest_plugin.py）
│   ├── scripts/              # 配置生成、数据库转换等一次性脚本
│   ├── locales/              # 核心自身的 i18n
│   ├── scheduler.py          # 调度器
│   ├── logger.py             # 日志
│   ├── alive.py              # 存活检测
│   ├── exports.py            # 导出系统
│   ├── i18n.py               # 国际化
│   ├── smtp.py               # 邮件发送
│   ├── version.py            # 版本信息
│   └── utils/                # 工具函数（cooldown / game / dirty_check / web_render / petal …）
│
├── bots/                     # 平台适配器
│   ├── onebot/               # QQ (OneBot)
│   ├── milky/                # QQ (Milky)
│   ├── qqbot/                # QQ (官方)
│   ├── discord/              # Discord
│   ├── telegram/             # Telegram
│   ├── kook/                 # KOOK
│   ├── matrix/               # Matrix
│   └── web/                  # Web
│
├── modules/                  # 命令模块
│   ├── core/                 # 核心模块（help, module, alias, prefix 等）
│   │   └── hooks/            # parser 入口 hook 的订阅实现（policies/tos/typo/routing…）
│   ├── wiki/                 # MediaWiki 查询
│   ├── arcaea/               # Arcaea 查询
│   ├── maimai/               # maimai 查询
│   ├── dice/                 # 骰子
│   └── ...                   # 更多模块
│
├── config/                   # 配置文件目录
│   ├── config.toml           # 主配置
│   ├── jobqueue.toml         # JobQueue 后端与 Hub 配置
│   ├── bot_*.toml            # 平台配置
│   └── module_*.toml         # 模块配置
│
├── assets/                   # 仓库自带的静态资源（字体、模板、config_store）
├── data/                     # 运行期数据（private/、i18n_cache/、filter_words/…）
├── database/                 # 数据库文件
├── tests/                    # 测试文件
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   ├── fixtures/             # HTTP fixture
│   └── run_one.py            # 单个测试入口的运行脚本
├── tester.py                 # 测试入口
├── tools/                    # 辅助脚本
├── example/                  # 示例
├── cache/ logs/              # 运行时产物（cache 每次启动被清空）
└── generated_docs/           # 生成的文档
```

> **注意**：`assets/` 存放仓库自带的静态资源（字体、模板、`config_store`），`data/` 存放运行期可写数据（`private/`、`i18n_cache/`、`filter_words/` 等）。两者职责不同，不要混用。
