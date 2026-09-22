---
name: akaribot-dev
description: AkariBot 项目开发指南。用于修改核心框架、消息与会话系统、命令模块、平台适配器、配置、数据库、队列、i18n、测试或项目约定；按任务领域读取对应 reference，不要一次加载全部文档。
---

# AkariBot 开发指南

先确定任务领域，再完整读取对应的一级参考文件。不要为了“了解项目”一次性加载全部 references；跨领域任务只组合读取确实相关的文件。

## 开始工作

1. 先读本文件中的强制规则。
2. 根据下方路由选择 reference，并完整读完所选文件后再改代码。
3. reference 中的行号、默认值和 API 只是工作入口；涉及具体实现时仍以当前源码为准，用 `rg` 核对。
4. 修改后按任务风险运行 Ruff 和自研测试框架。

## 强制规则

- 面向用户的固定文案使用 `I18NContext`，只在对应的 `locales/zh_cn.json` 新增或修改节点。参数占位符使用 `${name}`。
- 除非用户明确要求处理翻译或 Weblate 同步结果，禁止创建、修改、删除或补齐 `core/**/locales/`、`bots/**/locales/`、`modules/**/locales/` 中非 `zh_cn.json` 的语言 JSON。其他语言由 Weblate bot 自动提交。
- `assets/config_store/<语言>/` 是配置模板派生物；不要手改，应交给自动化生成。
- 新增配置字段时，在所属的 `zh_cn.json` 添加 `config.comments.<表名>.<字段名>`；未指定 `table_name` 时表名为 `config`。
- 会话归属的模块数据使用 `union_id` 和正确的 `union_scope`；不要新增按平台割裂的 `sender_id` / `target_id` 状态列。
- 平台能力必须使用 `Features(...)` 实例声明。不要子类化 `Features`，也不要把类对象赋给 `ContextManager.features`。
- `SessionInfo` 会跨进程传输，新增字段必须可序列化；模块代码运行在 server 进程，平台 SDK 操作必须通过 JobQueue / `ContextManager` 返回 bot 进程。
- 遇到循环导入时优先使用 `core.exports` 的导出机制，不要通过随意重排 import 掩盖问题。
- 测试以自研框架（`tester.py`）为准；根级 `conftest.py` 的 pytest 适配层兼容性差，不要依赖它。自动化运行必须设置 `CI=1`；否则人工复核和等待输入可能挂起。
- **不要在本地跑全量测试**，只跑与改动相关的文件或入口（`tests/run_one.py`）；全量是 CI 的职责。
- 文档、注释和配置说明只描述当前状态，不记录「从前如何」，不写「原本是 X，现在改为 Y」这类对照式表述。例外是为迁移历史数据而保留的兼容逻辑，以及 API 弃用标注。
- 不要给自明的代码写注释，也不要给非公开 API 加 docstring；注释只解释「为什么」，单条一般不超过三行，使用正式书面语而非口语。
- **不要擅自 commit**，所有改动留在未提交的工作区。除非用户明确授权，否则不执行 `git commit`，也不执行 `git add` / `push` / `reset` / `checkout -- <file>` 等改动暂存区、历史或丢弃工作区内容的操作；授权仅对当次请求有效。
- 新功能分支用 `dev/`，修复分支用 `fix/`；分支名使用英文。

## 按领域读取

| 任务 | 必须读取 | 典型内容 |
| --- | --- | --- |
| 理解整体架构、启动、进程、消息流或目录 | [architecture.md](references/architecture.md) | 双进程、JobQueue、启动与重启、收发消息全链路、目录结构 |
| 修改消息、会话、Bot 或 parser | [messaging-and-parser.md](references/messaging-and-parser.md) | Bot、消息元素、SessionInfo、MessageSession、ContextManager、parser、等待与控制流 |
| 修改 loader、component、配置、数据库或队列 | [infrastructure.md](references/infrastructure.md) | 模块加载、注册、配置模板、union 数据、双连接、JobQueue、exports、热重载 |
| 新建或修改命令模块 | [module-development.md](references/module-development.md) | module/command/regex、权限、配置、数据库、i18n、定时任务、hook、交互等待 |
| 新建或修改平台适配器 | [platform-adapters.md](references/platform-adapters.md) | info、Features、bot 入口、ContextManager、私信和平台能力 |
| 编写、运行或诊断测试 | [testing.md](references/testing.md) | `@func_case`、`@case`、Expectation、mock parser、fixture、单测命令 |
| 依赖、格式化、分支或文字排版 | [workflow-and-style.md](references/workflow-and-style.md) | Ruff、pre-commit、依赖、分支、中文排版、导入和注释约定 |

## 组合读取规则

- 修改普通命令：读 `module-development.md` + `messaging-and-parser.md`；补测试时再读 `testing.md`。
- 修改模块配置或数据库：读 `module-development.md` + `infrastructure.md`；若涉及消息入口，再读 `messaging-and-parser.md`。
- 修改消息元素、会话能力或 parser：读 `messaging-and-parser.md`；若行为影响命令模块，再读 `module-development.md` 和 `testing.md`。
- 修改平台发送、消息渲染或私信：读 `platform-adapters.md` + `architecture.md` + `messaging-and-parser.md`；涉及配置或队列细节时再读 `infrastructure.md`。
- 修改启动、队列或跨进程行为：读 `architecture.md` + `infrastructure.md`。
- 修改热重载：读 `infrastructure.md`；涉及守护进程重启时再读 `architecture.md`。
- 只改依赖、格式、分支或文案排版：读 `workflow-and-style.md`，不要加载其他大文件。

## 高频命令

```bash
uv sync
uv run ruff format .
uv run ruff check .

CI=1 uv run python tester.py
COVERAGE=1 CI=1 uv run python tester.py

CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py <测试文件> [入口函数]
```

`tester.py` 没有过滤参数。`tests/run_one.py` 强制 CI 模式并在收尾时使用 `os._exit`，不适合需要 `expected=None` 人工复核的用例。

## 常见陷阱

- 真实 parser 在 `core/builtins/parser/`，模块加载器在 `core/loader.py`，测试框架在 `core/tester/`；不要被只剩缓存的旧目录名误导。
- 测试 parser 不完整复现真实平台的模块启用、平台过滤和权限行为；测试通过不代表真实平台一定可达。
- Windows 下运行中文测试时显式设置 `PYTHONIOENCODING=UTF-8`。
- `.bot.lock` 阻止同一仓库启动第二个机器人实例。
- `pre_init()` 会清空整个 `cache/`，不要在那里保存需要持久化的数据。

## 参考文件维护

- 新增知识时放入最匹配的一个 reference，避免在多个文件复制同一段内容。
- 所有 reference 保持为本文件的直接链接，不建立二级引用链。
- reference 超过 100 行时保留顶部目录；若某一 reference 再次膨胀到难以按需读取，按更细领域继续拆分，并同步更新本路由。
- 修改 reference 后运行 `uv run python .agents/skills/akaribot-dev/scripts/validate_references.py` 校验：SKILL.md 行数、`references/` 链接是否有效、是否有孤立文件、长 reference 是否保留顶部目录，以及本文件是否仍覆盖几条必守规则。
