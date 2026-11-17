# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## 深入文档

`.agents/skills/akaribot-dev/SKILL.md` 是本项目的完整开发手册（架构详解、模块开发、平台适配器、i18n 规范等）。**本文件只记录高频命令与跨文件才能看清的架构脉络**，API 细节查阅该技能文件。

## 常用命令

```bash
uv sync --all-extras           # 安装依赖（平台适配器与模块的依赖按 packages/ 下的成员清单分组）
uv sync --extra modules-ai     # 只安装某个模块所需的依赖
uv add <包名> && uv lock       # 新增依赖（写入对应 packages/ 成员清单与根 pyproject 的 extra）
pre-commit install            # 安装 hook（自动跑 ruff check --fix / ruff format / uv export）

uv run ruff format .          # 格式化
uv run ruff check .           # 静态检查
uv run python tools/check_layers.py   # 依赖分层检查
uv run python tools/check_deps.py     # 成员清单与根项目依赖一致性检查

./start                       # 启动机器人（Windows 用 start.bat）
uv run --all-extras python bot.py   # 等价的直接启动方式
```

### 测试

单元测试在 `tests/unit/`，由 pytest 运行；集成测试在 `tests/integration/`，由仓库根的 `tester.py`（自研框架 `core/tester/`）运行。
> **不要在本地跑全量测试。** 项目单测数量很大，全量跑耗时且会拖慢迭代——那是 CI 的职责。本地只跑与改动相关的文件或入口。

```bash
uv run pytest tests/unit                        # 全部单元测试
uv run pytest tests/unit/test_message.py -q     # 单个文件
uv run pytest tests/unit -k markdown            # 按名字筛选

CI=1 AKARI_TEST_FILTER=test_wiki_diff uv run python tester.py   # 单个集成文件
CI=1 uv run python tester.py                                    # 全部整合测试（CI 用）
COVERAGE=1 CI=1 uv run python tester.py                         # 附带覆盖率报告（htmlcov/index.html）
```

全量测试由 CI 执行，本地只运行与改动相关的文件或入口。

pytest 侧：根 `conftest.py` 把 `assets/config_store/zh_cn` 铺到临时目录（`AKARI_CONFIG_PATH`）并叠加测试覆盖项，本机 `config/` 不参与测试；随后注册 `core/tester/pytest_plugin.py`。插件把 `tests/unit` 里 `@func_case` 标记的入口接管为 pytest 节点：会话开始时建库、加载模块与录制的 HTTP fixture，每个测试项开始前重建内存数据库与模块注册表，结束时回收遗留的后台任务，全程共用一个事件循环。单个测试默认超时 `120 × min(TIME_SCALE, 5)` 秒，可用 `@pytest.mark.akari_timeout(秒)` 或 `AKARI_TEST_TIMEOUT` 覆盖；测试中途需重建数据库时请求 `fresh_db` fixture。

两侧的用例写法相同：`@func_case` 标记入口，入口内用 `tester.integrate(输入, 期望)` 跑命令、`tester.test(函数, 说明)` 跑纯函数子测试。差别在于运行器：pytest 下 `tester.test` 直接以 pytest 断言失败结束（每个入口一个节点，首个失败即中止），`tester.py` 下则记录结果并在入口结束后统一汇报。

`@case(输入, 期望)` 可直接挂在命令定义上，由 `tester.py` 收集执行，函数本身仍是生产代码。

- **非交互运行设 `CI=1`**：无 `Expectation` 的用例默认走 `input()` 等待人工复核；`CI=1` 下转为 SKIP 并输出 `junit.xml`。
- **覆盖配置项用 `mock_config`**：`with mock_config(CoreConfig, use_emote=True):` 在进程内覆盖已声明的配置项，退出上下文即恢复。
- 集成测试断言器（`Match` / `Contains` / `Regex` / `AnyOutput` / `All` / `Not` …）见 `core/tester/expectations.py`。

集成测试使用 `core/tester/mock/parser.py` 中的简化版 `parser()`：它调用不带平台过滤的 `ModulesManager.return_modules_list()`，跳过模块启用检查，并将测试发送者设为 superuser。因此可用平台、启用状态与权限判定需单独针对相关逻辑验证。HTTP 请求由 `tests/fixtures/http/` 录制回放（`tests/capture_http_fixtures.py` 负责录制）。

#### 测试编写规范

- 按模块、适配器或子系统组织测试文件，同一行为的输入变体用循环或表驱动归并，变更或移除功能时同步更新测试与 `tests/fixtures/`。
- 只断言对外可观察行为（返回值、发出的消息、持久化结果、权限与安全判定），不绑定私有实现、mock 调用次数或日志原文。
- 纯函数逻辑用单元测试覆盖；集成测试（`tests/integration/`）用于验证命令主路径与关键错误分支。
- `_test_` 辅助函数需通过 `tester.test` 注册执行；涉及等待与超时时使用 `core.tester.timing.TIME_SCALE`。

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

`core/component.py` 的 `module()` 返回 `Bind.Module`，其上挂 `.command()` / `.regex()` / `.schedule()` / `.hook()` / `.handle()` / `.config()` 装饰器。`core/loader.py` 的 `ModulesManager` 从 `core/plugin.py` 的注册表取模块包（entry point 优先，未安装时回退为扫描 `modules` 命名空间包），导入时 `__init__.py` 里的 `module()` 调用完成注册，之后从数据库恢复启用状态。支持 `reload_module()` 热重载。

命令模板语法：`<必需参数>`、`[-flag <可选参数>]`、`...`（变长）、`{{I18N:key}}`（帮助描述）。参数落在 `msg.parsed_msg` 字典里。

### 依赖分层与 workspace 成员

仓库是 uv workspace，也是 monorepo：`packages/` 下每个平台适配器与模块各是一个可安装的发行版，源码位于 `packages/<成员>/src/<导入路径>`（`akari-bot-core` → `core`、`akari-bot-adapter-<平台>` → `bots.<平台>`、`akari-bot-module-<模块>` → `modules.<模块>`）。成员各自声明依赖并以 entry point 注册（`akari.bots` / `akari.modules`），根 `pyproject.toml` 的 `dependencies` 只依赖 `akari-bot-core`，再按 `bots-<平台>`、`modules-<模块>` 的 extra 聚合各成员。全量安装用 `uv sync --all-extras`，子集安装用 `uv sync --extra <名称>`。

运转期发现集中在 `core/plugin.py`：entry point 优先，未安装时回退扫描 `bots` / `modules` 命名空间包，因此插件可以来自仓库外的独立发行版。locale、配置模板与模块数据表都从注册表项推导路径，不再按目录硬编码。

依赖方向由 `tools/check_layers.py` 强制：`core` 不得依赖插件，`bots/*` 不得依赖 `modules/*`，`modules/*` 只能使用 core 公开 API 且不得依赖平台 SDK（白名单在脚本内），`tools/layers_baseline.json` 记录待清理的既有越界，只允许缩减。`tools/check_deps.py` 校验成员清单、entry point 与根项目 extra 的一致性。两者都在 CI 的测试任务中执行。

### 循环导入的规避

`core/exports.py` 提供全局 `exports` 字典。核心类（如 `Bot`）通过 `add_export(Bot)` 注册，被依赖方用 `from core.exports import exports; Bot = exports["Bot"]` 取回。遇到循环导入时优先使用该机制。

### 会话四件套

理解模块开发必须同时看这四个文件（都在 `core/builtins/session/`）：`info.py` 的 `SessionInfo`（可序列化的会话身份 + 平台能力标志）、`internal.py` 的 `MessageSession`（传给模块函数的对象，`send_message` / `wait_confirm` / 权限检查）、`context.py` 的 `ContextManager`（平台适配器要实现的抽象基类）、`features.py` 的 `Features`（平台声明支持哪些能力，会被注入进 `SessionInfo`）。

### 数据库

Tortoise ORM，**双连接**：`default`（可配 MySQL）+ `local`（本地 SQLite）。模块可在 `modules/<模块>/database/models.py` 定义自己的模型，`init_db()` 自动发现注册。`bot.py` 的 `pre_init()` 按 `DBVersion` 做迁移。

## 项目约定

### 只描述当前状态

- 文档、注释和配置说明只描述当前状态与设计取舍，不写历史对比；变更历史由 git 承载。
- 代码中为迁移历史数据而保留的兼容逻辑（如旧配置表名、数据库版本升级路径、退役客户端的数据迁移）需保留并注明适用范围；API 弃用标注同样保留。

### 注释与文档

- 只在逻辑涉及反直觉的边界情况、hack、复杂算法或特定业务规则时写注释，解释“为什么”而非实现细节；单条一般不超过三行，使用正式书面语。非公开 API 不加 docstring。
- 文档面向技术用户与维护者，覆盖功能概述、基本使用步骤和接口实现。

### i18n 与本地化

- 模块面向用户的文案统一使用 `I18NContext("key", **参数)`，只在对应组件的 `locales/zh_cn.json` 新增或修改节点（简体中文）。调试日志等非用户文案可用纯文本。
- 其他语言的 `locales/*.json` 由 Weblate 自动同步，`assets/config_store/<语言>/` 由配置模板派生，均无需手动修改。
- 新增配置字段时，在模板所属组件的 `zh_cn.json` 添加 `config.comments.<表名>.<字段名>`（核心写 `core/locales/`，平台写 `bots/<平台>/locales/`，模块写 `modules/<模块>/locales/`），注释只描述用途。表名随装饰器而定（`config` / `secret` / `bot_<平台>` / `module_<模块>`，`secret=True` 时带 `_secret` 后缀）；`@on_base_config()` 的表外顶层键无表名层级。

### 版本控制

- 改动留在工作区，仅在用户明确授权时执行 `git commit` 等版本控制写操作。
- 分支：新功能 `dev/` 前缀，修 bug `fix/` 前缀，英文命名。

### 其他

- Ruff：行宽 120、双引号，忽略 E402/F405/F403/E741/E721。
- 中文排版：中英文之间加空格、全角标点、称呼用户用“你”、机器人自称用“机器人”、第三人称用“它”。
- 默认命令前缀 `~` / `～`。
- 获取时间统一走 `core.utils.timezone` 或 `SessionInfo.now()` / `today()`，用户展示用 `msg.format_time()` / `FormattedTime`。

## 陷阱

- **Windows 下输出中文乱码**：`bot.py` / `tester.py` 里的 `os.environ.setdefault("PYTHONIOENCODING", "UTF-8")` 在解释器启动后才执行，来不及生效。在启动命令前显式加 `PYTHONIOENCODING=UTF-8`（`start.bat` 用 `chcp 65001` 加显式赋值达到同样目的）。
- **`.bot.lock` 单实例锁**：`bot.py` 用文件锁拒绝第二个实例，报 `Another instance is already running`。调试时确认没有残留进程占着锁。
- `pre_init()` 每次启动会清空整个 `cache/` 目录。
- **配置只在可写进程中补写**：`pre_init()` 与 `core.scripts.config_generate` 可写，之后守护进程置位 `AKARI_CONFIG_READONLY=1` 再 spawn 子进程，bot 与 server 只读。新增配置项后需重启机器人使配置补写生效。
- **常用目录位置**：导入名为准，物理路径统一为 `packages/<成员>/src/<导入路径>`。parser 在 `core/builtins/parser/`，模块加载器是 `core/loader.py`，测试框架在 `core/tester/`；配置系统实现在 `core/builtins/config/`，配置模板在 `core/config/`；`cooldown` / `game` / `dirty_check` / `web_render` 等通用设施在 `core/utils/`，TOS 处理在 `modules/core/hooks/tos.py`。
