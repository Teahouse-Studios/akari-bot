# 测试指南

## 目录

- [测试框架](#91-测试框架)
- [断言类型](#92-断言类型)
- [测试环境的真实行为](#93-测试环境的真实行为)
- [测试规范](#94-测试规范)
- [运行测试](#95-运行测试)

---

## 9. 测试指南

### 9.1 测试框架

AkariBot 使用内置测试框架，实现在 `core/tester/`，入口是仓库根的 `tester.py`。仓库根的 `conftest.py` 与 `core/tester/pytest_plugin.py` 仅作 pytest 适配层，日常单测统一使用 `tests/run_one.py`（见 §9.5），**不要在本地跑全量测试**，全量测试由 CI 执行。

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

`Tester` 提供两个断言方法：

```python
async def integrate(self, input_, expected=None, note=None, timeout=None)
# 集成测试：input_ 是命令字符串（或字符串列表 = 连续多条消息），
# expected 传 Expectation；为 None 时框架转为人工复核

async def test(self, func, note=None)
# 纯函数测试：func 返回真值即通过，支持同步/异步
```

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

测试使用 `core/tester/mock/parser.py` 中的简化版 `parser()`，与生产环境有两个主要差异：

1. 使用不带平台过滤参数的 `ModulesManager.return_modules_list()`，且不检查模块是否已启用，集成测试可直接发送命令而无需先 `~module enable <模块>`。
2. `run_test_case()` 将测试发送者设为 superuser，mock 权限检查默认通过。

因此改动涉及 `available_for` / `exclude_from`、模块启用状态或权限判定时，需单独针对相关逻辑验证。

其他环境替身位于 `core/tester/mock/`：`database`（内存库）、`loader`（模块加载）、`random`（固定随机种子）、`fixtures`（HTTP 响应回放）、`config`（配置项覆盖）。

需要让某个配置项取非默认值时用 `mock_config`，它在进程内以叠加来源的方式替换配置读取（底层是 `core.builtins.config.interface.use_source()`），退出上下文即恢复原值：

```python
from core.config.core import CoreConfig
from core.tester import mock_config

with mock_config(CoreConfig, use_emote=True, enable_petal=False):
    ...
```

也可以写成 `with tester.mock_config(...)`。字段名须是该模板类已声明的配置项，支持嵌套使用。

测试引导会将落盘目录重定向到临时路径：配置从 `assets/config_store/zh_cn` 复制到临时目录（`AKARI_CONFIG_PATH`）并叠加测试覆盖项，不读取仓库的 `config/`；`tester.py` 在铺设完成后调用 `bootstrap_config()` 加载配置，晚于此的模板导入才能取到配置项。union 合并日志写入临时目录（`AKARI_UNION_MERGE_LOGS_PATH`）并在结束时清理（若已显式设置该环境变量则保留）。

### 9.4 测试规范

- 优先使用 `Contains()` 等具体断言校验关键输出，少用宽泛的 `AnyOutput()`。
- 断言对外可观察行为，不绑定私有属性、内部调用次数或提示文案的完整措辞；结构化返回值优先做必需字段的子集断言。
- 涉及外部网络的模块使用 `tests/capture_http_fixtures.py` 录制 fixture，在测试中离线回放。

### 9.5 运行测试

**运行单个测试文件或入口**：使用 `tests/run_one.py`。第二个参数是入口函数名；省略时运行该文件中所有以 `test_` 开头的入口。脚本会自动补充 `sys.path` 并在结束时调用 `os._exit`。

```bash
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py tests/unit/test_action_text.py test_action_text_kecode
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py tests/unit/test_message.py
```

**全量测试（CI 使用）**：

```bash
CI=1 uv run python tester.py              # 跑全部测试
COVERAGE=1 CI=1 uv run python tester.py   # 附带覆盖率报告（htmlcov/index.html）
```

自动化运行需设置 `CI=1`：非 CI 模式下，无 `expected` 的用例或交互输入耗尽时会调用 `input()` 等待人工输入；CI 模式会跳过人工复核项并输出 `junit.xml`。`MAX_CONCURRENT`（`tester.py`，值为 `1`）限制 `@case` 用例的并发，`@func_case` 按顺序执行。

CI 环境默认设置 `AKARI_TEST_TIME_SCALE=10` 放宽超时；Windows 或 Git Bash 下若输出乱码，在命令前显式设置 `PYTHONIOENCODING=UTF-8`。CI 工作流见 `.github/workflows/run-builtin-tester.yml`。

---

