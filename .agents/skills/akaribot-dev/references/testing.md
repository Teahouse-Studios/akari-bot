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

单元测试在 `tests/unit/`，由 pytest 运行；集成测试在 `tests/integration/`，由仓库根的 `tester.py` 运行。两者共用 `core/tester/` 下的测试设施（mock、断言器、JUnit 输出）。全量测试由 CI 执行。

```
tests/
├── unit/           # pytest 单元测试（纯函数）
├── integration/    # @func_case 集成测试（走完整命令链路）
├── fixtures/       # HTTP 响应等录制的 fixture
├── helpers/        # RPC worker 等测试辅助进程
├── run_one.py      # 跑单个集成入口
└── capture_http_fixtures.py   # 录制 HTTP fixture 的工具脚本
```

**两侧的用例写法相同**：用 `@func_case` 标记入口，入口接收 `tester: Tester`，入口内用 `tester.test` 跑纯函数子测试、用 `tester.integrate` 跑命令。差别只在运行器：`tests/unit/` 由 pytest 运行，`tests/integration/` 由 `tester.py` 运行。

```python
from core.tester import func_case, Tester, Contains


def _test_iter_splits_surrounding_text():
    return len(list(iter_at_code("hi <AT:QQ|123> bye"))) == 3


@func_case
async def test_atcode(tester: Tester):
    """AT 码解析与渲染测试"""
    await tester.test(_test_iter_splits_surrounding_text, "AT 码与文本交替切分")
    return tester
```

pytest 下每个 `@func_case` 入口是一个测试节点，`tester.test` 内部以 pytest 断言失败结束（`AssertionError` 带上说明或原始异常），因此入口内首个失败即中止；`tester.py` 下则记录每条子测试结果并在入口结束后统一汇报，失败不中断后续子测试。

```python
from core.tester import func_case, Tester, Contains


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
# 集成入口内的纯函数子测试：func 返回真值即通过，支持同步/异步
```

临时验证一条命令时不必另写入口：用 `@case` 把案例直接挂在命令定义上，`tester.py` 会一并收集执行。

```python
from core.tester import case, Match


@case("~test say Hello", Match("Hello is Hello"))
@test.command("say <word>")
async def _(msg: Bot.MessageSession, word: str):
    await msg.finish(f"{word} is {msg.parsed_msg['<word>']}")
```

`@case` 的参数与 `tester.integrate` 一致（输入、期望、说明、超时）；被装饰的函数仍是生产代码，案例只在测试运行期生效。

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

两个 runner 共用同一套环境铺设：配置从 `assets/config_store/zh_cn` 复制到临时目录（`AKARI_CONFIG_PATH`）并叠加测试覆盖项，不读取仓库的 `config/`；union 合并日志写入临时目录（`AKARI_UNION_MERGE_LOGS_PATH`）并在结束时清理（已显式设置该环境变量时保留）。根 `conftest.py`、`tester.py` 与 `tests/run_one.py` 在导入 `core.*` 前通过 `tester.py` 的 `prepare_test_environment()` 完成铺设。

pytest 侧由 `core/tester/pytest_plugin.py` 在会话开始时建库、加载模块、语言包与录制的 HTTP 响应；全程只有一个事件循环。每个测试项开始前重建内存数据库并调用 `ModulesManager.refresh()`（模块注册表与 hook 订阅是进程级状态），结束时取消它遗留的后台任务。单个测试默认超时 `120 × min(TIME_SCALE, 5)` 秒，可用 `@pytest.mark.akari_timeout(秒)` 或环境变量 `AKARI_TEST_TIMEOUT` 覆盖，超时会取消该测试并判为失败；需要测试中途重建数据库时请求 `fresh_db` fixture。

集成测试使用 `core/tester/mock/parser.py` 中的简化版 `parser()`，与生产环境有两个主要差异：

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

### 9.4 测试规范

- 单元测试用 `assert` 断言可观察的返回值；集成测试优先使用 `Contains()` 等具体断言校验关键输出，少用宽泛的 `AnyOutput()`。
- 断言对外可观察行为，不绑定私有属性、内部调用次数或提示文案的完整措辞；结构化返回值优先做必需字段的子集断言。
- 涉及外部网络的模块使用 `tests/capture_http_fixtures.py` 录制 fixture，在测试中离线回放。

### 9.5 运行测试

**单元测试**（pytest）：

```bash
uv run pytest tests/unit                       # 全部
uv run pytest tests/unit/test_message.py -q     # 单个文件
uv run pytest tests/unit -k markdown            # 按名字筛选
```

CI 下设 `AKARI_TEST_TIME_SCALE=10` 放宽超时；Windows 或 Git Bash 下若输出乱码，在命令前显式设置 `PYTHONIOENCODING=UTF-8`。

**集成测试**（`tester.py`）：`AKARI_TEST_FILTER` 可按路径子串筛选单个文件；`tests/run_one.py` 可跑单个入口（第二个参数是入口函数名，省略时跑该文件中所有以 `test_` 开头的入口，脚本会补充 `sys.path` 并在结束时调用 `os._exit`）。

```bash
CI=1 AKARI_TEST_FILTER=test_wiki_diff uv run python tester.py
CI=1 PYTHONIOENCODING=UTF-8 uv run --no-sync python tests/run_one.py tests/integration/test_features_command.py
CI=1 uv run python tester.py              # 跑全部集成测试并输出 junit.xml
COVERAGE=1 CI=1 uv run python tester.py   # 附带覆盖率报告（htmlcov/index.html）
```

非交互运行集成测试需设 `CI=1`：非 CI 模式下，无 `expected` 的用例或交互输入耗尽时会调用 `input()` 等待人工输入；CI 模式会跳过人工复核项。

CI 工作流见 `.github/workflows/run-builtin-tester.yml`：先跑 `pytest tests/unit`（输出 `junit-unit.xml`），再跑 `tester.py`（输出 `junit.xml`），两份报告一并上送。

---

