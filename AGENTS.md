# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## 深入文档

`.agents/skills/akaribot-dev/SKILL.md` 是本项目的完整开发手册（架构详解、模块开发、平台适配器、i18n 规范等）。**本文件只记录高频命令与跨文件才能看清的架构脉络**；需要 API 细节时读那份技能文件，不要重复其内容。

## 常用命令

```bash
uv sync                       # 安装依赖
uv add <包名> && uv lock       # 新增依赖（需移到 pyproject.toml 对应注释分组内并按字母序排列）
pre-commit install            # 安装 hook（自动跑 ruff check --fix / ruff format / uv export）

uv run ruff format .          # 格式化
uv run ruff check .           # 静态检查

./start                       # 启动机器人（Windows 用 start.bat）
uv run python bot.py          # 等价的直接启动方式
```

### 测试

项目使用**自研测试框架**（`core/tester/`），入口是仓库根的 `tester.py`。测试位于 `tests/unit/`（纯函数）和 `tests/integration/`（命令交互）。

仓库根另有 `conftest.py` 和 `core/tester/pytest_plugin.py`，把 `@func_case` 入口接到了 pytest 上。但**这只是适配层，兼容性差**，不要依赖它：日常跑单测一律优先用 `tests/run_one.py`，遇到行为差异以 `tester.py` 为准。

> **不要在本地跑全量测试。** 项目单测数量很大，全量跑耗时且会拖慢迭代——那是 CI 的职责。本地只跑与改动相关的文件或入口。

```bash
# 跑单个入口
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py tests/unit/test_action_text.py test_action_text_kecode
# 省略第二个参数则跑该文件的全部入口
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py tests/unit/test_message.py
```

该脚本会补 `sys.path`（以文件路径启动时项目根不在其中），并在收尾时 `os._exit` —— 框架加载的模块会留下未完成的后台任务，正常返回会一直挂到超时。

全量入口（**CI 用**，`tester.py` 会 glob `tests/**/*.py` 全跑，没有过滤参数）：

```bash
CI=1 uv run python tester.py              # 跑全部测试；CI=1 是必需的
COVERAGE=1 CI=1 uv run python tester.py   # 附带覆盖率报告（htmlcov/index.html）
```

- **不加 `CI=1` 会挂起**：无 `Expectation` 的用例会走 `input()` 等人工复核。`CI=1` 下这些用例转为 SKIP，并输出 `junit.xml`。
- **首次运行前需要有配置**：`config/` 为空时 `bot.py` 会自动生成；CI 里的做法是 `mkdir -p config && cp -r assets/config_store/zh_cn/* config/`。

测试用例的两种写法：`@func_case` 标记的 `async def test_x(tester: Tester)`，内部用 `tester.integrate(输入, 期望)` 跑命令、`tester.test(函数)` 跑纯函数；或用 `@case(输入, 期望)` 直接装饰在 `@mod.command` 上。断言器（`Match` / `Contains` / `Regex` / `AnyOutput` / `All` / `Not` …）见 `core/tester/expectations.py`。

**测试走的不是生产 `parser()`**，而是 `core/tester/mock/parser.py` 里的简化版：它用不带平台过滤的 `ModulesManager.return_modules_list()`，**不检查模块是否已启用**；`run_test_case()` 还会把测试发送者建成 superuser。所以集成测试里直接 `~wiki` 就能跑，无需先 `~module enable wiki`——但反过来，**测试通过不代表该命令在真实平台上可达**（可用平台、启用状态、权限都没被覆盖）。HTTP 请求由 `tests/fixtures/http/` 的录制回放（`tests/capture_http_fixtures.py` 负责录制）。

## 架构脉络

### 多进程 + 可切后端的 JobQueue

`bot.py` 是**守护进程**，本身不处理消息。它 spawn 出：

- 每个启用的平台一个 **bot 子进程**（`bots/{platform}/bot.py`，由各自的 `config/bot_<平台>.toml` 里 `[bot_<平台>].enable` 决定）
- 一个 **server 子进程**（`core/server/run.py`）
- JobQueue 选 websocket 后端且为内置模式时，额外一个 **`jobqueue-hub` 子进程**（先于 bot/server 启动，最后关闭）

进程间**不共享内存**，全靠 `core/queue/` 的 Peer RPC 与信号总线通信。后端由 `config/jobqueue.toml` 的 `[jobqueue].jobqueue_backend` 选择，生产可选 `database`（落 `JobQueuesTable` 轮询）和 `websocket`（经 Hub 实时路由）；两套后端的 Registry 与 Transport 不得交叉组合，也不会自动回退。跨进程调用在 `core/queue/contracts.py` 用 `@remote()` / `@signal()` / `context_method()` 声明契约，在接收进程侧 `.bind(JobQueueClient/JobQueueServer)` 注册实现。

这解释了几件反直觉的事：`SessionInfo` 必须能序列化；模块代码跑在 server 进程里，拿不到平台 SDK 对象，只能通过 JobQueue 让 bot 进程代为操作（删消息、禁言、加表情等）。

守护进程按**退出码**决定重启策略：`0` = 正常退出不重启；`33` = 重启全部 bot；`78` = 明确无需重启，摘掉该进程；其他 = 重启该 bot（60 秒内失败 3 次则放弃）。server 进程退出码 `0` 会让整个守护进程 `sys.exit(0)`，其他非 `33` 码则带该码退出。

### 消息全链路

平台 SDK → `bots/{platform}/bot.py` 构造 `SessionInfo` → `Bot.process_message()` 注入平台 `Features` 并登记 context → JobQueue → server 侧 `parser()`（`core/builtins/parser/message.py`：刷新会话 → 前缀匹配 → 模板解析 → 模块匹配 → 执行）→ 模块函数 → `msg.finish()` 抛 `SessionFinished` → JobQueue 回传 → `ContextManager.send_message()` 发出。

**parser 的策略行为由 hook 承载**（`core/builtins/parser/hooks/`）。parser 主干只负责解析与派发，权限拦截、TOS 限流、错字纠正、频道去重等都作为订阅挂在 `HookPoint` 上，实现在 `modules/core/hooks/`（`policies.py` / `tos.py` / `typo.py` / `routing.py` …）。例如 rapidfuzz 错字纠正在 `modules/core/hooks/typo.py`，订阅 `COMMAND_UNMATCHED`。改解析期行为前先确认该行为归属 parser 主干还是某个 hook 订阅。

### 模块注册

`core/component.py` 的 `module()` 返回 `Bind.Module`，其上挂 `.command()` / `.regex()` / `.schedule()` / `.hook()` / `.handle()` / `.config()` 装饰器。`core/loader.py` 的 `ModulesManager` 用 `pkgutil` 扫 `modules/`，导入时 `__init__.py` 里的 `module()` 调用完成注册，之后从数据库恢复启用状态。支持 `reload_module()` 热重载。

命令模板语法：`<必需参数>`、`[-flag <可选参数>]`、`...`（变长）、`{{I18N:key}}`（帮助描述）。参数落在 `msg.parsed_msg` 字典里。

### 循环导入的规避

`core/exports.py` 提供全局 `exports` 字典。核心类（如 `Bot`）通过 `add_export(Bot)` 注册，被依赖方用 `from core.exports import exports; Bot = exports["Bot"]` 取回。**遇到循环导入时优先用这个机制，不要重排 import。**

### 会话四件套

理解模块开发必须同时看这四个文件（都在 `core/builtins/session/`）：`info.py` 的 `SessionInfo`（可序列化的会话身份 + 平台能力标志）、`internal.py` 的 `MessageSession`（传给模块函数的对象，`send_message` / `wait_confirm` / 权限检查）、`context.py` 的 `ContextManager`（平台适配器要实现的抽象基类）、`features.py` 的 `Features`（平台声明支持哪些能力，会被注入进 `SessionInfo`）。

### 数据库

Tortoise ORM，**双连接**：`default`（可配 MySQL）+ `local`（本地 SQLite）。模块可在 `modules/<模块>/database/models.py` 定义自己的模型，`init_db()` 自动发现注册。`bot.py` 的 `pre_init()` 按 `DBVersion` 做迁移。

## 项目约定

### 只描述当前状态

- **文档、注释和配置说明只描述当前状态，不记录「从前如何」。** 不要写「原本是 X，现在改为 Y」「已迁移到 Z」「不再使用 W」这类对照式表述，直接陈述当下的事实与约束。
- 变更历史由 git 承载。需要解释设计取舍时，说明当前为何如此，而不是叙述它从什么演变而来。
- **例外**：代码中为迁移历史数据而保留的兼容逻辑（如旧配置表名、数据库版本升级路径、退役客户端的数据迁移）应当保留，并注明其适用范围。这类兼容是当前行为的一部分，不属于「记录从前」。
- 标注某个 API 已弃用属于陈述当前状态，可以保留。

### 注释

- **不要给自明的代码写注释。** 注释解释「为什么」，不解释「是什么」或实现细节。
- 只有在逻辑涉及反直觉的边界情况、hack、复杂算法或特定业务规则时才写注释。
- **单条注释一般不超过三行。** 写不下说明该抽函数或补文档，不要在代码里堆长篇说明。
- **使用正式书面语**，不得出现口语化表达（如「这里坑爹」「先这样吧」「TODO：回头再说」）、语气词、感叹号或调侃。
- 不要给非公开 API 的模块、类、函数加 docstring。

### 文档

- 文档面向技术用户与维护者，不面向初学者或照教程操作的人。
- 只覆盖功能概述、基本使用步骤和接口实现。
- 不要逐步讲解内部工作原理或技术细节。

### i18n 与本地化

- **i18n 强制**：模块内**禁止**对用户输出纯文本，一律 `I18NContext("key", **参数)`，并只在 `modules/<模块>/locales/zh_cn.json` 建节点（zh_cn 是必需的基础语言）。仅调试日志等不面向用户的场景可用纯文本。
- **本地化文本只写简体中文**，不要提供其他语言的翻译。
- **禁止改其他语言文件**：除非用户明确要求处理翻译或 Weblate 同步结果，不得创建、修改、删除或补齐 `core/**/locales/`、`bots/**/locales/`、`modules/**/locales/` 中 `zh_cn.json` 以外的语言 JSON。其他语言由 Weblate bot 自动提交，即使缺少新键也不要复制简体中文或自行翻译。`assets/config_store/<语言>/` 是配置模板派生物，非 `zh_cn` 版本也不要手改，应交给自动化生成。
- **新增配置字段必须补注释**：配置项在模板类里声明（`core/config/decorator.py` 的 `@on_base_config` / `@on_config` / `@on_bot_config` / `@on_module_config`），同时要在**模板所属组件**的 `zh_cn.json` 里加 `config.comments.<表名>.<字段名>`——核心写 `core/locales/`，平台写 `bots/<平台>/locales/`，模块写 `modules/<模块>/locales/`。表名随装饰器而定（`config` / `secret` / `bot_<平台>` / `module_<模块>`，`secret=True` 时带 `_secret` 后缀）；`@on_base_config()` 的表外顶层键没有表名这一层。
- **配置项注释视作文档**：只描述该项的用途，不描述技术细节。

### 版本控制

- **不要擅自 commit。** 所有改动都留在未提交的工作区，交由用户自行检视与提交。
- 除非用户明确授权自动提交，否则不执行 `git commit`；`git add`、`git push`、`git reset`、`git checkout -- <file>` 等会改动暂存区、历史或丢弃工作区内容的操作同样需要用户授权。
- 授权仅对当次请求有效，不要据此推定后续改动也可以自动提交。
- 分支：新功能 `dev/` 前缀，修 bug `fix/` 前缀，命名用英文。

### 其他

- Ruff：行宽 120、双引号，忽略 E402/F405/F403/E741/E721。
- 中文排版：中英文之间加空格、全角标点、称呼用户用“你”、机器人自称用“机器人”而非“我”、第三人称用“它”。
- 默认命令前缀 `~` / `～`。

## 陷阱

- **Windows 下输出中文乱码**：`bot.py` / `tester.py` 里的 `os.environ.setdefault("PYTHONIOENCODING", "UTF-8")` 在解释器启动后才执行，来不及生效。在启动命令前显式加 `PYTHONIOENCODING=UTF-8`（`start.bat` 用 `chcp 65001` 加显式赋值达到同样目的）。
- **`.bot.lock` 单实例锁**：`bot.py` 用文件锁拒绝第二个实例，报 `Another instance is already running`。调试时确认没有残留进程占着锁。
- `pre_init()` 每次启动会 **`rmtree` 整个 `cache/` 目录**，别往里放需要留存的东西。
- **配置只在 `pre_init()` 里补写**：之后守护进程会置位 `AKARI_CONFIG_READONLY=1` 再 spawn 子进程，bot 与 server 一律只读。所以**新增配置项后必须重启机器人**，否则子进程读到该键会抛 `ConfigOperationError`。
- **按目录名找文件容易扑空**：parser 在 `core/builtins/parser/`，模块加载器是 `core/loader.py` 这个文件，测试框架在 `core/tester/`；`cooldown` / `game` / `dirty_check` / `web_render` 等通用设施在 `core/utils/`，TOS 处理在 `modules/core/hooks/tos.py`。
