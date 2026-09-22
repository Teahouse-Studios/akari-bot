# 测试指南

## 目录

- [测试框架](#91-测试框架)
- [断言类型](#92-断言类型)
- [测试环境的真实行为](#93-测试环境的真实行为)
- [测试规范](#94-测试规范)
- [运行测试](#95-运行测试)

本文件只说明测试框架和运行方式。修改测试时，还要读取被测功能所属的 reference；不要从测试 mock 反推生产 API。

---

## 9. 测试指南

### 9.1 测试框架

AkariBot 使用内置测试框架，实现在 `core/tester/`，入口是仓库根的 `tester.py`。

仓库根另有 `conftest.py`，配合 `core/tester/pytest_plugin.py` 把 `@func_case` 入口接到 pytest 上（dev 依赖含 `pytest` / `pytest-asyncio`，`pyproject.toml` 里有 `[tool.pytest.ini_options]`）。但**这只是适配层，兼容性差**，不要依赖它：日常跑单测一律优先用 `tests/run_one.py`（见 §9.5），遇到行为差异以 `tester.py` 为准。

> **不要在本地跑全量测试。** 项目单测数量很大，全量跑耗时且会拖慢迭代——那是 CI 的职责。本地只跑与改动相关的文件或入口。

测试文件放在 `tests/` 下，`tester.py` 用 `tests/**/*.py` 递归收集：

```
tests/
├── unit/           # 纯函数单元测试
├── integration/    # 走完整命令链路的集成测试
├── fixtures/       # HTTP 响应等录制的 fixture
├── helpers/        # RPC worker 等测试辅助进程
├── run_one.py      # 跑单个测试文件 / 入口
└── capture_http_fixtures.py   # 录制 HTTP fixture 的工具脚本
```

有两种写法。

**写法一：`@func_case` + `Tester`**（`tests/` 下的主流写法）

一个被 `@func_case` 标记的 async 函数就是一个测试用例，接收 `tester: Tester`。现有用例通常在末尾 `return tester`；框架也会从传入的 tester 收集结果，因此省略返回仍可运行，但新用例保持该惯例更清晰：

```python
from core.tester import func_case, Tester, Contains, Empty


@func_case
async def test_version(tester: Tester):
    """version 命令测试"""
    await tester.integrate("~version", Contains("版本"), "version 应输出版本信息")
    return tester
```

`Tester` 只有两个下断言的方法：

```python
async def integrate(self, input_, expected=None, note=None, timeout=None)
# 集成测试：input_ 是命令字符串（或字符串列表 = 连续多条消息），
# expected 传 Expectation；为 None 时框架转为人工复核

async def test(self, func, note=None)
# 纯函数测试：func 返回真值即通过，支持同步/异步
```

> 注意：**没有 `tester.expect()`**。

**写法二：`@case` 装饰器**（把用例直接挂在命令定义上）

```python
from core.tester import case, Match


@case("~test say Hello", Match("Hello is Hello"))
@test.command("say <word>")
async def _(msg: Bot.MessageSession, word: str):
    await msg.finish(f"{word} is {msg.parsed_msg['<word>']}")
```

### 9.2 断言类型

全部定义在 `core/tester/expectations.py`，均继承 `Expectation`：

| 断言                    | 用途                             |
| ----------------------- | -------------------------------- |
| `Match(text)`           | 渲染后的消息文本精确匹配         |
| `Equal(message)`        | 可发送消息链完全相等             |
| `Contains(text)`        | 包含匹配                         |
| `ContainsAll(*texts)`   | 全部包含                         |
| `ContainsAny(*texts)`   | 任一包含                         |
| `StartsWith(text)`      | 前缀匹配                         |
| `EndsWith(text)`        | 后缀匹配                         |
| `Regex(pattern)`        | 正则匹配                         |
| `InOrder(*types)`       | 指定消息元素类型按顺序出现       |
| `Length(...)`           | 消息链元素总数校验               |
| `Count(type, ...)`      | 指定消息元素类型数量校验         |
| `OutputCount(...)`      | 平台 action 条目数量校验         |
| `Exist(type, func=None)`| 存在指定消息元素类型             |
| `StructureEqual(*types)`| 元素数量、顺序和类型严格一致     |
| `AnyOutput()`           | 有输出即可                       |
| `Empty()`               | 无输出                           |
| `Raise(exc)`            | 期望抛出异常                     |
| `NoException()`         | 期望不抛异常                     |
| `ActionContains(...)`   | 校验产生的平台动作（撤回/禁言等）|
| `Predicate(func)`       | 自定义函数                       |
| `All(...)`              | AND 组合                         |
| `Any(...)`              | OR 组合                          |
| `Not(...)`              | NOT 取反                         |

### 9.3 测试环境的真实行为

**测试走的不是生产 `parser()`**，而是 `core/tester/mock/parser.py` 里的简化版。两个关键差异：

1. 它用不带平台过滤参数的 `ModulesManager.return_modules_list()`，且**不检查模块是否已启用** —— 所以集成测试里**不需要**先 `~module enable <模块>`，直接发命令就能命中。
2. `run_test_case()` 会把测试发送者建成 **superuser**，mock 权限检查也大多直接通过 —— 所以许多权限受限的命令在测试里仍能跑通。

反过来说：**测试通过不代表该命令在真实平台上可达**。模块级、命令级和正则级的平台过滤行为并不一致，模块开关与真实平台权限也没有被完整覆盖；改动涉及 `available_for` / `exclude_from` / 启用状态 / 权限时要另行确认。

其他环境替身在 `core/tester/mock/` 下：`database`（内存库）、`loader`（模块加载）、`random`（固定随机种子）、`fixtures`（HTTP 响应回放）。需要覆盖 Config 时用 `unittest.mock.patch`。

测试引导还会把会落盘的内容移出仓库：整份配置来自临时目录（`AKARI_CONFIG_PATH`），union 合并日志写进临时目录（`AKARI_UNION_MERGE_LOGS_PATH`）并在收尾时删除。用例会真实走到合并流程，不隔离的话每次测试运行都会在 `data/union_merge_logs/` 里留下大量合成的快照。需要留存这些日志时自行设置 `AKARI_UNION_MERGE_LOGS_PATH` 指向保留目录即可，已显式设置的值优先。

### 9.4 测试规范

- 避免使用 `AnyOutput()`，尽量用 `Contains()` 校验关键内容
- 发现疑似 Bug 时提醒用户检查，不自行修复
- 涉及网络的模块先用 `tests/capture_http_fixtures.py` 录 fixture，再让测试离线回放

### 9.5 运行测试

**跑单个测试（日常默认做法）**：`tester.py` 没有筛选参数，使用仓库内的 `tests/run_one.py`。第二个参数是入口函数名；省略时运行该文件中所有以 `test_` 开头的入口。脚本会补项目根到 `sys.path`，并在收尾时用 `os._exit` 强制退出，避免框架遗留的后台任务导致进程挂起。

```bash
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py tests/unit/test_action_text.py test_action_text_kecode
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py tests/unit/test_message.py
```

`tests/run_one.py` 强制使用 CI 模式，不适合需要 `expected=None` 人工复核的用例。

**全量入口（CI 用，不要在本地跑）**：

```bash
CI=1 uv run python tester.py              # 跑全部测试
COVERAGE=1 CI=1 uv run python tester.py   # 附带覆盖率报告（htmlcov/index.html）
```

**自动化运行必须设置 `CI=1`**：非 CI 模式下，没有 `expected` 的用例和等待交互输入耗尽的用例可能调用 `input()`，在非交互终端里直接卡死。CI 模式会跳过需要人工复核的项目，交互输入不足则失败而不是等待。`MAX_CONCURRENT`（`tester.py`，值为 `1`）限制 `@case` 用例的并发；`@func_case` 始终按顺序执行。完整测试还会生成 `junit.xml`。

CI 另外设了 `AKARI_TEST_TIME_SCALE=10` 来放宽超时，本地复现 CI 上的超时类失败时可以照搬。

Git Bash 下如果输出是乱码，在命令前加 `PYTHONIOENCODING=UTF-8` —— `tester.py` 里的 `os.environ.setdefault` 在解释器启动后才执行，对 stdout 编码已经来不及了。

CI 工作流见 `.github/workflows/run-builtin-tester.yml`。

---

