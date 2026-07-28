# 配置生成的进程隔离 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把配置文件的生成收敛到 `bot.py` 的 `pre_init()` 一处，bot 与 server 子进程默认只读，仅经一组显式的 `edit_*` 接口供交互式编辑命令写入。

**Architecture:** 新增环境变量 `AKARI_CONFIG_READONLY`，守护进程在 spawn 子进程之前置位，`core/config/__init__.py` 在导入期读取。只读时 `CFGManager.write()` / `delete()` / `save()` 抛 `ConfigOperationError`，配置模板导入时跳过补写，配置版本迁移的导入被跳过。`pre_init()` 调用新增的 `core/config/scan.py` 扫描全部模板补全缺键，失败则中止启动。

**Tech Stack:** Python 3.12、tomlkit、loguru、自研测试框架（`core/tester/`，非 pytest）。

## Global Constraints

- **不要 `git commit`。** 每个任务做完停下即可，提交由用户自行决定。计划中没有 commit 步骤，这是刻意的。
- 面向用户的输出一律走 `I18NContext`，本计划涉及的全部消息均为日志与异常，用英文纯文本即可。
- 注释与 docstring 一律正式书面语，参数说明用 `:param x:` / `:return:` / `:raises X:` 风格。
- Ruff：行宽 120、双引号。改完跑 `./.venv/Scripts/ruff.exe format .` 与 `./.venv/Scripts/ruff.exe check .`。
- 测试跑法：`CI=1 PYTHONIOENCODING=UTF-8 ./.venv/Scripts/python.exe tester.py`。**不加 `CI=1` 会挂起**。
- 测试基线有 20 个既有失败（`test_arcaea` / `test_mcmod` / `test_tweet_not_found` / `test_wiki_headers_manage` / `test_wiki_not_found` / `test_wiki_page_info` / `test_wiki_prefix_manage` / `test_wiki_search` / `test_locale_set` / `test_version_sys` / `test_emojimix` / `test_idlist` / `test_idlist_not_found` / `test_nbnhhsh` / `test_nbnhhsh_not_found` / `test_minecraft_news` / `test_dice_complex` / `test_hash_md5` / `test_hash_sha256` / `test_tos`），**用差集比对，不看绝对数量**。`test_mcserver` 会抖动（打真实的 `mc.hypixel.net`），出现即忽略。
- 测试禁止触碰真实的 `config/` 目录，一律用 `CFGManager.switch_config_path()` 切到临时目录并在结束时还原。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `core/config/__init__.py`（改） | `CONFIG_READONLY` 常量、版本迁移导入的闸门、`CFGManager.readonly`、`_allow_write_depth`、`_writable()`、`_ensure_writable()`、`edit_write()`、`edit_delete()`，以及 `write()` / `delete()` / `save()` 的守卫 |
| `core/config/decorator.py`（改） | 只读时跳过补写配置文件，`__config_fields__` 的登记照常 |
| `core/config/scan.py`（新） | `scan_config_templates()`，导入全部配置模板补全缺键，返回失败列表 |
| `bot.py`（改） | `pre_init()` 调用扫描并按结果中止；`CoreConfig` 导入下沉进 `pre_init()`；spawn 前后的环境变量管理；`multiprocess_run_until_complete()` 传播退出码 |
| `modules/core/su_utils.py`（改） | `~config write` / `~config delete` 改调 `edit_write` / `edit_delete` |
| `bots/web/client.py`（改） | jwt_secret 自举改调 `edit_write` |
| `tests/unit/test_config_readonly.py`（新） | 只读语义与授权写入的单元测试 |
| `tests/unit/test_config_template.py`（改） | 追加「`core/config` 之外不得直接调用 `CFGManager` 写方法」的仓库不变量断言 |

---

## Task 1: 只读闸门与授权写入 API

**Files:**
- Modify: `core/config/__init__.py`
- Test: `tests/unit/test_config_readonly.py`（本任务创建）

**Interfaces:**
- Consumes: 无
- Produces:
  - `core.config.CONFIG_READONLY_ENV: str` —— 环境变量名，值为 `"AKARI_CONFIG_READONLY"`
  - `core.config.CONFIG_READONLY: bool` —— 导入期一次性求值的模块级常量
  - `CFGManager.readonly: bool` —— 运行期判据，测试可直接改写
  - `CFGManager._allow_write_depth: int`
  - `CFGManager._writable()` —— 可重入的上下文管理器
  - `CFGManager._ensure_writable(q: str | None = None, table_name: str | None = None, secret: bool = False) -> None`
  - `CFGManager.edit_write(q: str, value: Any | None, cfg_type: type | tuple | None = None, secret: bool = False, table_name: str | None = None) -> None`
  - `CFGManager.edit_delete(q: str, table_name: str | None = None) -> bool`

- [ ] **Step 1: 写失败的测试**

创建 `tests/unit/test_config_readonly.py`：

```python
"""配置只读语义与授权写入的单元测试。

配置的生成统一由 bot.py 的 pre_init() 完成，bot 与 server 子进程一律只读，
以免同一批配置项被多个进程重复补写。本组测试守住这一约束。
"""

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from core.config import CFGManager
from core.constants.exceptions import ConfigOperationError
from core.tester import func_case, Tester

# 最小可用的配置文件内容，含表外顶层键、普通表与密钥表各一
MINIMAL_CONFIG = """default_locale = "zh_cn"
config_version = 3

[config]
debug = false

[secret]
db_path = "sqlite://database/save.db"
"""


@contextmanager
def _temp_config(readonly: bool):
    """把 CFGManager 切到一份临时配置上，退出时完整还原。

    :param readonly: 期间的只读标志。
    :return: 临时配置目录的路径。
    """
    original_path = CFGManager.config_path
    original_values = CFGManager.values
    original_tss = CFGManager._tss
    original_file_list = CFGManager.config_file_list
    original_readonly = CFGManager.readonly

    tmp = Path(tempfile.mkdtemp(prefix="akari_cfg_readonly_"))
    try:
        (tmp / "config.toml").write_text(MINIMAL_CONFIG, encoding="utf-8")
        CFGManager.switch_config_path(tmp)
        CFGManager.readonly = readonly
        yield tmp
    finally:
        CFGManager.readonly = original_readonly
        CFGManager.config_path = original_path
        CFGManager.values = original_values
        CFGManager._tss = original_tss
        CFGManager.config_file_list = original_file_list
        shutil.rmtree(tmp, ignore_errors=True)


def _test_readonly_write_raises():
    """只读时 write() 应抛 ConfigOperationError，且不改动内存中的配置"""
    with _temp_config(readonly=True):
        before = CFGManager.values["config"]["config"].get("debug")
        try:
            CFGManager.write("debug", True, bool, False, "config")
        except ConfigOperationError:
            return CFGManager.values["config"]["config"].get("debug") == before
        return False


def _test_readonly_delete_raises():
    """只读时 delete() 应抛 ConfigOperationError"""
    with _temp_config(readonly=True):
        try:
            CFGManager.delete("debug", "config")
        except ConfigOperationError:
            return "debug" in CFGManager.values["config"]["config"]
        return False


def _test_readonly_save_raises():
    """只读时 save() 应抛 ConfigOperationError"""
    with _temp_config(readonly=True):
        try:
            CFGManager.save()
        except ConfigOperationError:
            return True
        return False


def _test_readonly_get_missing_key_with_default_raises():
    """只读时读取缺失的键会触发回写默认值，应抛 ConfigOperationError"""
    with _temp_config(readonly=True):
        try:
            CFGManager.get("brand_new_key", "fallback", str, False, "config")
        except ConfigOperationError:
            return True
        return False


def _test_readonly_get_missing_key_without_default_returns_none():
    """只读时读取缺失且无默认值的键不写盘，应返回 None 而非抛错"""
    with _temp_config(readonly=True):
        return CFGManager.get("another_new_key", None, str, False, "config") is None


def _test_readonly_load_still_works():
    """只读时 load() 应正常，能读到磁盘上的新值"""
    with _temp_config(readonly=True) as tmp:
        path = tmp / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("debug = false", "debug = true"), encoding="utf-8")
        CFGManager.load()
        return CFGManager.values["config"]["config"]["debug"] is True


def _test_edit_write_succeeds_in_readonly():
    """edit_write() 在只读进程中应成功写盘"""
    with _temp_config(readonly=True) as tmp:
        CFGManager.edit_write("debug", True, bool, False, "config")
        return "debug = true" in (tmp / "config.toml").read_text(encoding="utf-8")


def _test_edit_delete_succeeds_in_readonly():
    """edit_delete() 在只读进程中应成功删除并写盘"""
    with _temp_config(readonly=True) as tmp:
        deleted = CFGManager.edit_delete("debug", "config")
        return deleted and "debug" not in (tmp / "config.toml").read_text(encoding="utf-8")


def _test_writable_scope_restores_readonly():
    """edit_* 结束后应恢复只读，计数归零"""
    with _temp_config(readonly=True):
        CFGManager.edit_write("debug", True, bool, False, "config")
        if CFGManager._allow_write_depth != 0:
            return False
        try:
            CFGManager.write("debug", False, bool, False, "config")
        except ConfigOperationError:
            return True
        return False


def _test_writable_process_can_write():
    """非只读进程中 write() 应照常成功"""
    with _temp_config(readonly=False) as tmp:
        CFGManager.write("debug", True, bool, False, "config")
        return "debug = true" in (tmp / "config.toml").read_text(encoding="utf-8")


@func_case
async def test_config_readonly(tester: Tester):
    """core.config: 配置只读语义测试"""
    await tester.test(_test_readonly_write_raises, "只读时 write 抛错测试")
    await tester.test(_test_readonly_delete_raises, "只读时 delete 抛错测试")
    await tester.test(_test_readonly_save_raises, "只读时 save 抛错测试")
    await tester.test(_test_readonly_get_missing_key_with_default_raises, "只读时读缺键带默认值抛错测试")
    await tester.test(_test_readonly_get_missing_key_without_default_returns_none, "只读时读缺键无默认值返回 None 测试")
    await tester.test(_test_readonly_load_still_works, "只读时 load 正常测试")
    await tester.test(_test_edit_write_succeeds_in_readonly, "edit_write 授权写入测试")
    await tester.test(_test_edit_delete_succeeds_in_readonly, "edit_delete 授权删除测试")
    await tester.test(_test_writable_scope_restores_readonly, "授权作用域退出后恢复只读测试")
    await tester.test(_test_writable_process_can_write, "非只读进程写入正常测试")

    return tester
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
CI=1 PYTHONIOENCODING=UTF-8 ./.venv/Scripts/python.exe - <<'EOF' 2>&1 | grep -E "RUN|ERROR"
import asyncio, importlib.util, sys
from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.process import run_function_entry
async def main():
    await init_db()
    await load_modules(show_logs=False, monkey_patches={"Random": Random()})
    spec = importlib.util.spec_from_file_location("t", "tests/unit/test_config_readonly.py")
    mod = importlib.util.module_from_spec(spec); sys.modules["t"] = mod
    spec.loader.exec_module(mod)
    res = await run_function_entry(mod.test_config_readonly, is_ci=True)
    for r in res.get("results", []): print("RUN", r.get("note"), "->", r.get("match"))
    if res.get("error"): print("ERROR:", res.get("error"))
    await close_db()
asyncio.run(main())
EOF
```

Expected: `ERROR:` 一行，内容形如 `AttributeError: type object 'CFGManager' has no attribute 'readonly'`。

- [ ] **Step 3: 加入模块级常量与版本迁移的闸门**

`core/config/__init__.py`：在 `import core.config.update  # noqa`（第 23 行）**之前**插入。注意 `class CFGManager` 从第 33 行才开始，此处取不到类属性，故须用模块级常量。

```python
# 环境变量名。守护进程在 spawn 子进程之前置位，spawn 会继承环境。
# 该闸门须赶在 core.config 被导入之前生效：core/config/update.py 的版本迁移是导入期执行的，
# 而 go() 里的 Info.subprocess = True 来得太晚——它前面的 core.logger 已经把 core.config 拉起来了。
CONFIG_READONLY_ENV = "AKARI_CONFIG_READONLY"
CONFIG_READONLY = bool(os.environ.get(CONFIG_READONLY_ENV))

# 配置版本迁移只应发生在 pre_init 中。core.config.update 全仓仅此一处导入且为纯副作用导入，
# 跳过它即可，无需改动其内部那段顶层代码。
if not CONFIG_READONLY:
    import core.config.update  # noqa
```

把原来的 `import core.config.update  # noqa` 那一行删掉（已被上面的条件导入取代）。`os` 已在第 2 行导入，无需新增。

在文件顶部的 import 区补上：

```python
import multiprocessing
```

- [ ] **Step 4: 加入 CFGManager 的只读状态与守卫**

`core/config/__init__.py`，在 `class CFGManager` 的类属性区（`_lock_depth = 0` 之后、`LOCK_TIMEOUT` 之前）插入：

```python
    # 本进程是否只读。运行期一律读这个类属性而非模块级常量，测试可直接改写。
    readonly: bool = CONFIG_READONLY
    # 授权写入的嵌套深度。用计数而非布尔：write() 内部会调用 save()，两层都须放行。
    _allow_write_depth = 0
```

在 `_exclusive()` 之后插入两个方法：

```python
    @classmethod
    @contextmanager
    def _writable(cls):
        """临时解除只读限制，仅供 edit_* 使用。可重入。"""
        cls._allow_write_depth += 1
        try:
            yield
        finally:
            cls._allow_write_depth -= 1

    @classmethod
    def _ensure_writable(cls, q: str | None = None, table_name: str | None = None, secret: bool = False):
        """在只读进程中拒绝写入。

        配置的生成统一由 bot.py 的 pre_init() 完成，bot 与 server 子进程一律只读，
        以免同一批配置项被多个进程重复补写。交互式编辑须经 edit_write() / edit_delete()。

        :param q: 配置项键名，仅用于组装错误信息。
        :param table_name: 配置项表名，仅用于组装错误信息。
        :param secret: 是否为密钥配置项，仅用于组装错误信息。
        :raises ConfigOperationError: 当前进程只读，且不处于授权写入的作用域内。
        """
        if not cls.readonly or cls._allow_write_depth:
            return
        process_name = multiprocessing.current_process().name
        if q:
            target = table_name or ("secret" if secret else "config")
            detail = f'write "{q}" to table "{target}"'
        else:
            detail = "save config files"
        raise ConfigOperationError(
            f"Config is read-only in process {process_name!r}, cannot {detail}. "
            "Missing keys must be generated in pre_init."
        )
```

- [ ] **Step 5: 在三个持久化入口装上守卫**

`save()`：在方法体最前、`with cls._exclusive():` 之前插入。

```python
    @classmethod
    def save(cls):  # Save the config files
        cls._ensure_writable()
        with cls._exclusive():
```

`delete()`：在 `q = q.lower()` 之后、`found = False` 之前插入。须早于任何对 `cls.values` 的改动。

```python
        cls.watch()
        q = q.lower()
        cls._ensure_writable(q, table_name)
        found = False
```

`write()`：插在 `if value is None: ... return` 这一段**之后**、`with cls._exclusive():` 之前。

不能放在方法体最前——无默认值的读取（如 `Config("default_locale", cfg_type=str)`）会以 `value=None` 走到这里并提前返回，本就不写盘，不应抛错。

```python
            else:  # if the value is None, skip to autofill
                logger.debug(f"[Config] Config {q} has no default value, skipped to auto fill.")
                return

        cls._ensure_writable(q, table_name, secret)

        # 「重新加载 → 修改 → 保存」须在同一个临界区内完整完成。
        # 否则本进程会以过时的内存副本整体覆盖磁盘，致使其它进程期间写入的配置项丢失。
        with cls._exclusive():
```

- [ ] **Step 6: 加入 edit_* 授权接口**

`core/config/__init__.py`，插在 `delete()` 之后、`switch_config_path()` 之前：

```python
    @classmethod
    def edit_write(
        cls,
        q: str,
        value: Any | None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
    ):
        """授权写入，供交互式编辑命令与启动期的密钥自举使用。

        这是只读进程中唯一合法的写入途径。命名为 edit_* 而非给 write() 加参数，
        是为了让 grep 能穷举全部合法写入点。

        :param q: 配置项键名。
        :param value: 修改值。
        :param cfg_type: 配置项类型。
        :param secret: 是否为密钥配置项。（默认为False）
        :param table_name: 配置项表名。
        """
        with cls._writable():
            cls.write(q, value, cfg_type, secret, table_name)

    @classmethod
    def edit_delete(cls, q: str, table_name: str | None = None) -> bool:
        """授权删除，供交互式编辑命令使用。

        :param q: 配置项键名。
        :param table_name: 配置项表名。
        :return: 配置项是否被删除。
        """
        with cls._writable():
            return cls.delete(q, table_name)
```

- [ ] **Step 7: 跑测试确认通过**

重跑 Step 2 的命令。Expected: 10 行 `RUN ... -> True`，无 `ERROR`。

- [ ] **Step 8: 跑 lint**

```bash
./.venv/Scripts/ruff.exe format core/config/ tests/unit/test_config_readonly.py && ./.venv/Scripts/ruff.exe check core/config/ tests/
```

Expected: `All checks passed!`

---

## Task 2: 模板导入在只读进程中跳过补写

**Files:**
- Modify: `core/config/decorator.py`
- Test: `tests/unit/test_config_readonly.py`（追加一条）

**Interfaces:**
- Consumes: `CFGManager.readonly`（Task 1）
- Produces: 无新符号。行为约定为：只读时 `_process_class()` 仍完整填充 `__config_fields__`，但不调用 `CFGManager.has()` / `get(_generate=True)` / `save()`

- [ ] **Step 1: 写失败的测试**

在 `tests/unit/test_config_readonly.py` 中，`_test_writable_process_can_write` 之后追加：

```python
def _test_readonly_template_registers_without_writing():
    """只读时导入配置模板应完成字段登记，但不产生任何写入"""
    from core.config.decorator import on_config

    with _temp_config(readonly=True) as tmp:
        before = (tmp / "config.toml").read_text(encoding="utf-8")

        @on_config("probe", "module")
        class ProbeConfig:
            probe_value: int = 42

        fields_registered = set(ProbeConfig.__config_fields__) == {"probe_value"}
        no_new_file = not (tmp / "module_probe.toml").exists()
        unchanged = (tmp / "config.toml").read_text(encoding="utf-8") == before
        return fields_registered and no_new_file and unchanged
```

并在 `test_config_readonly` 的注册列表末尾追加：

```python
    await tester.test(_test_readonly_template_registers_without_writing, "只读时模板登记不写盘测试")
```

- [ ] **Step 2: 跑测试确认它失败**

重跑 Task 1 Step 2 的命令。Expected: 最后一行 `RUN 只读时模板登记不写盘测试 -> False`（模板导入触发了 `has()` 与 `save()`，`save()` 抛错被 `_process_class` 冒泡出来，或写出了 `module_probe.toml`）。

- [ ] **Step 3: 在生成循环中跳过补写**

`core/config/decorator.py` 的 `__generate_config_file()` 内，在 `config_fields[attr_name] = {...}` 这段**之后**、`if not CFGManager.has(...)` 之前插入：

```python
                # 只读进程不补写配置文件：生成统一在 bot.py 的 pre_init() 中完成，
                # 以免每个子进程重新导入模板时重复补写同一批配置项。
                # 字段登记必须照做，否则模板类属性无法读取。
                if CFGManager.readonly:
                    continue

                # 检查配置项是否已存在于目标表中，不存在时才补写
```

- [ ] **Step 4: 跑测试确认通过**

重跑 Task 1 Step 2 的命令。Expected: 11 行 `RUN ... -> True`，无 `ERROR`。

- [ ] **Step 5: 跑 lint**

```bash
./.venv/Scripts/ruff.exe format core/config/ && ./.venv/Scripts/ruff.exe check core/config/
```

Expected: `All checks passed!`

---

## Task 3: 配置模板扫描

**Files:**
- Create: `core/config/scan.py`
- Test: `tests/unit/test_config_scan.py`（本任务创建）

**Interfaces:**
- Consumes: `CFGManager.save()`（Task 1 已加守卫）
- Produces:
  - `core.config.scan.iter_config_template_modules() -> list[str]` —— 列出全部配置模板的模块名，不产生任何导入
  - `core.config.scan.scan_config_templates() -> list[str]` —— 返回加载失败的配置模板模块名列表，空列表表示全部成功

**实现前必读——测试环境中不能断言「扫描补全了缺失键」。** 测试进程里 `core.config.base` 与 `modules/*/config` 已被 tester 的 `load_modules()` 导入过，`importlib.import_module()` 会直接返回缓存的模块而**不再执行** `_process_class()`，因此扫描不会向临时配置目录补写任何东西。生产环境不受影响：`pre_init` 跑在全新 spawn 出的进程里，Task 5 又把 `bot.py` 顶层的 `CoreConfig` 导入下沉了，模块缓存基本是空的。

所以把「发现哪些模板」与「导入模板会补写」拆成两件事分别测：前者由 `iter_config_template_modules()` 承担，是不含副作用的纯逻辑；后者是 `_process_class()` 的职责，用测试内现场声明的模板来验证。

- [ ] **Step 1: 写失败的测试**

创建 `tests/unit/test_config_scan.py`：

```python
"""配置模板扫描的单元测试。"""

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from core.config import CFGManager
from core.config.scan import scan_config_templates
from core.tester import func_case, Tester

MINIMAL_CONFIG = """default_locale = "zh_cn"
config_version = 3

[config]
debug = false

[secret]
db_path = "sqlite://database/save.db"
"""


@contextmanager
def _temp_config():
    """把 CFGManager 切到一份空白的临时配置上，退出时完整还原。

    :return: 临时配置目录的路径。
    """
    original_path = CFGManager.config_path
    original_values = CFGManager.values
    original_tss = CFGManager._tss
    original_file_list = CFGManager.config_file_list
    original_readonly = CFGManager.readonly

    tmp = Path(tempfile.mkdtemp(prefix="akari_cfg_scan_"))
    try:
        (tmp / "config.toml").write_text(MINIMAL_CONFIG, encoding="utf-8")
        CFGManager.switch_config_path(tmp)
        CFGManager.readonly = False
        yield tmp
    finally:
        CFGManager.readonly = original_readonly
        CFGManager.config_path = original_path
        CFGManager.values = original_values
        CFGManager._tss = original_tss
        CFGManager.config_file_list = original_file_list
        shutil.rmtree(tmp, ignore_errors=True)


def _test_scan_covers_every_template_file():
    """磁盘上每个 config.py 都应被列入扫描范围，不得静默跳过"""
    import bots
    import modules

    expected = {"core.config.base"}
    for package in (bots, modules):
        package_path = Path(package.__path__[0])
        for entry in sorted(package_path.iterdir()):
            if entry.is_dir() and (entry / "config.py").exists():
                expected.add(f"{package.__name__}.{entry.name}.config")

    return set(iter_config_template_modules()) == expected


def _test_scan_reports_no_failure():
    """仓库内全部配置模板都应能加载"""
    with _temp_config():
        return scan_config_templates() == []


def _test_scan_writes_template_fields():
    """扫描所在的可写进程中，模板导入应把声明的字段补进配置文件"""
    from core.config.decorator import on_config

    # 已被 tester 导入过的模板不会再执行 _process_class，故用现场声明的模板验证补写行为
    with _temp_config() as tmp:
        @on_config("scanprobe", "module")
        class ScanProbeConfig:
            scan_probe_value: int = 7

        del ScanProbeConfig
        written = (tmp / "module_scanprobe.toml")
        return written.exists() and "scan_probe_value = 7" in written.read_text(encoding="utf-8")


@func_case
async def test_config_scan(tester: Tester):
    """core.config.scan: 配置模板扫描测试"""
    await tester.test(_test_scan_covers_every_template_file, "扫描覆盖全部模板文件测试")
    await tester.test(_test_scan_reports_no_failure, "全部模板可加载测试")
    await tester.test(_test_scan_writes_template_fields, "可写进程中模板补写字段测试")

    return tester
```

`_test_scan_covers_every_template_file` 是这三条里最要紧的一条：它直接盯住「有没有模板被静默跳过」，而这正是漏键的唯一来源。它不含任何导入副作用，因此不受模块缓存影响。

导入行改为：

```python
from core.config.scan import iter_config_template_modules, scan_config_templates
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
CI=1 PYTHONIOENCODING=UTF-8 ./.venv/Scripts/python.exe - <<'EOF' 2>&1 | grep -E "RUN|ERROR"
import asyncio, importlib.util, sys
from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.process import run_function_entry
async def main():
    await init_db()
    await load_modules(show_logs=False, monkey_patches={"Random": Random()})
    spec = importlib.util.spec_from_file_location("t", "tests/unit/test_config_scan.py")
    mod = importlib.util.module_from_spec(spec); sys.modules["t"] = mod
    spec.loader.exec_module(mod)
    res = await run_function_entry(mod.test_config_scan, is_ci=True)
    for r in res.get("results", []): print("RUN", r.get("note"), "->", r.get("match"))
    if res.get("error"): print("ERROR:", res.get("error"))
    await close_db()
asyncio.run(main())
EOF
```

Expected: `ERROR:` 一行，内容形如 `ModuleNotFoundError: No module named 'core.config.scan'`（导入失败发生在模块加载阶段，三条用例都跑不到）。

- [ ] **Step 3: 实现扫描**

创建 `core/config/scan.py`：

```python
"""配置模板扫描。

配置的生成统一在 bot.py 的 pre_init() 中完成，bot 与 server 子进程一律只读，
因此这里必须把全部模板扫全：任何遗漏的键都会在子进程读取时抛出 ConfigOperationError。
"""

import importlib
import pkgutil
from pathlib import Path

from loguru import logger

from core.config import CFGManager


def iter_config_template_modules() -> list[str]:
    """列出全部配置模板的模块名。

    以文件是否存在判断有无模板，而非在导入时捕获 ModuleNotFoundError：后者分不清
    「该 bot 或模块本就没有 config.py」与「模板自身 import 了不存在的依赖」，
    第二种会被静默跳过，正是本设计要杜绝的漏键。

    也不用 importlib.util.find_spec()——它会为了取得 __path__ 而导入父包，
    把整个 bot 或模块包及其依赖全拉起来，正好抵消配置模板作为叶子模块带来的好处。

    :return: 配置模板的模块名列表，核心配置排在最前。
    """
    import bots
    import modules

    names = ["core.config.base"]
    for package in (bots, modules):
        package_path = Path(package.__path__[0])
        for submodule in pkgutil.iter_modules(package.__path__):
            if (package_path / submodule.name / "config.py").exists():
                names.append(f"{package.__name__}.{submodule.name}.config")
    return names


def scan_config_templates() -> list[str]:
    """导入全部配置模板，补全配置文件中缺失的键。

    扫描不区分 bot 与模块的启用状态：配置项一律补全，否则用户先禁用再启用便会撞上缺键。

    :return: 加载失败的配置模板模块名列表，空列表表示全部成功。
    """
    failed = []
    for module_name in iter_config_template_modules():
        try:
            importlib.import_module(module_name)
        except Exception:
            failed.append(module_name)
            logger.exception(f"[Config] Failed to load config template {module_name}: ")
    CFGManager.save()
    return failed
```

- [ ] **Step 4: 跑测试确认通过**

重跑 Step 2 的命令。Expected: 3 行 `RUN ... -> True`，无 `ERROR`。

- [ ] **Step 5: 跑 lint**

```bash
./.venv/Scripts/ruff.exe format core/config/ tests/unit/test_config_scan.py && ./.venv/Scripts/ruff.exe check core/ tests/
```

Expected: `All checks passed!`

---

## Task 4: 调用点改用授权写入

**Files:**
- Modify: `modules/core/su_utils.py:693`、`modules/core/su_utils.py:699`
- Modify: `bots/web/client.py:44`
- Test: `tests/unit/test_config_template.py`（追加一条仓库不变量断言）

**Interfaces:**
- Consumes: `CFGManager.edit_write()` / `CFGManager.edit_delete()`（Task 1）
- Produces: 无新符号

- [ ] **Step 1: 写失败的测试**

在 `tests/unit/test_config_template.py` 中，`_test_module_config_table_matches_module_name` 之后追加：

```python
def _test_no_unauthorized_config_write_call_sites():
    """core/config 与一次性脚本之外，不得直接调用 CFGManager 的写入方法"""
    forbidden_methods = {"write", "delete", "save"}
    offenders = []
    for path, relative in _iter_python_files():
        # core/scripts/ 下是离线运行的一次性脚本，不在 bot 进程内，允许直接写入
        if relative.parts[:2] == ("core", "scripts"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden_methods
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "CFGManager"
            ):
                offenders.append(f"{relative.as_posix()}:{node.lineno}  {ast.unparse(node)}")
    if offenders:
        Logger.error(f"[配置模板] 以下调用绕过了只读限制，请改用 CFGManager.edit_write / edit_delete：{offenders}")
        return False
    return True
```

并在 `test_config_template` 的注册列表末尾追加：

```python
    await tester.test(_test_no_unauthorized_config_write_call_sites, "无未授权配置写入调用点测试")
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
CI=1 PYTHONIOENCODING=UTF-8 ./.venv/Scripts/python.exe - <<'EOF' 2>&1 | grep -E "RUN|ERROR"
import asyncio, importlib.util, sys
from core.tester.mock.database import init_db, close_db
from core.tester.mock.loader import load_modules
from core.tester.mock.random import Random
from core.tester.process import run_function_entry
async def main():
    await init_db()
    await load_modules(show_logs=False, monkey_patches={"Random": Random()})
    spec = importlib.util.spec_from_file_location("t", "tests/unit/test_config_template.py")
    mod = importlib.util.module_from_spec(spec); sys.modules["t"] = mod
    spec.loader.exec_module(mod)
    res = await run_function_entry(mod.test_config_template, is_ci=True)
    for r in res.get("results", []): print("RUN", r.get("note"), "->", r.get("match"))
    if res.get("error"): print("ERROR:", res.get("error"))
    await close_db()
asyncio.run(main())
EOF
```

Expected: 最后一行 `RUN 无未授权配置写入调用点测试 -> False`，日志中列出 `bots/web/client.py:44`、`modules/core/su_utils.py:693`、`modules/core/su_utils.py:699`。

- [ ] **Step 3: 改 su_utils 的两处**

`modules/core/su_utils.py` 的 `~config write` 命令，把

```python
    CFGManager.write(k, v, secret=secret, table_name=table_name)
```

改为

```python
    CFGManager.edit_write(k, v, secret=secret, table_name=table_name)
```

`~config delete` 命令，把

```python
    if CFGManager.delete(k, table_name):
```

改为

```python
    if CFGManager.edit_delete(k, table_name):
```

`~config get` 不动：它不传默认值，`write()` 会在 `value is None` 处提前返回，不会触发只读守卫。

- [ ] **Step 4: 改 web 的 jwt_secret 自举**

`bots/web/client.py`，把

```python
    CFGManager.write("jwt_secret", Random.randbytes(32).hex(), secret=True, table_name="bot_web")
```

改为

```python
    # jwt_secret 须在 web 子进程首次启动时随机生成并持久化，属只读进程中的合法写入
    CFGManager.edit_write("jwt_secret", Random.randbytes(32).hex(), secret=True, table_name="bot_web")
```

- [ ] **Step 5: 跑测试确认通过**

重跑 Step 2 的命令。Expected: 7 行 `RUN ... -> True`，无 `ERROR`。

- [ ] **Step 6: 跑 lint**

```bash
./.venv/Scripts/ruff.exe format . && ./.venv/Scripts/ruff.exe check .
```

Expected: `All checks passed!`

---

## Task 5: bot.py 接线

**Files:**
- Modify: `bot.py:26`（删除顶层的 `CoreConfig` 导入）
- Modify: `bot.py:81-129`（`pre_init()`）
- Modify: `bot.py:132-141`（`multiprocess_run_until_complete()`）
- Modify: `bot.py:168-172`（`run_bot()` 开头）

**Interfaces:**
- Consumes: `core.config.CONFIG_READONLY_ENV`（Task 1）、`core.config.scan.scan_config_templates()`（Task 3）
- Produces: 无新符号。行为约定为：`pre_init` 子进程可写，bot 与 server 子进程只读，`pre_init` 非零退出即中止守护进程

- [ ] **Step 1: 把 CoreConfig 的导入下沉进 pre_init**

`bot.py` 第 26 行删除：

```python
from core.config.base import CoreConfig
```

理由：`multiprocessing` 以 spawn / forkserver 启动子进程时会把主模块以 `__mp_main__` 重新导入一遍，这一行会在每个子进程里再次触发配置模板的生成。它只在 `pre_init()` 内部的两处用到（原第 93、117 行），下沉即可让守护进程与全部子进程的顶层都不再触碰配置模板。

- [ ] **Step 2: 在 pre_init 中调用扫描**

`bot.py` 的 `pre_init()`，把

```python
    from core.constants.version import database_version
    from core.database.link import get_db_link
    from core.database.models import SenderInfo, DBVersion

    Logger.info(ascii_art)
    if CoreConfig.debug:
        Logger.debug("Debug mode is enabled.")
```

改为

```python
    from core.config.base import CoreConfig
    from core.config.scan import scan_config_templates
    from core.constants.version import database_version
    from core.database.link import get_db_link
    from core.database.models import SenderInfo, DBVersion

    Logger.info(ascii_art)

    # 配置的生成集中在此完成：子进程一律只读，此处遗漏的键会在子进程读取时抛错，
    # 因此任何模板加载失败都必须中止启动，而不是留到运行期才暴露。
    failed_templates = scan_config_templates()
    if failed_templates:
        Logger.critical(f"Failed to load config templates: {failed_templates}. Aborting.")
        sys.exit(1)

    if CoreConfig.debug:
        Logger.debug("Debug mode is enabled.")
```

- [ ] **Step 3: 让 pre_init 的失败传播出来**

`bot.py` 的 `multiprocess_run_until_complete()`，把

```python
def multiprocess_run_until_complete(func):
    mp = multiprocessing.get_context("spawn" if sys.platform in ["win32", "darwin"] else "forkserver")
    p = mp.Process(target=func, daemon=True)
    p.start()

    while True:
        if not p.is_alive():
            break
        time.sleep(1)
    terminate_process(p)
```

改为

```python
def multiprocess_run_until_complete(func):
    mp = multiprocessing.get_context("spawn" if sys.platform in ["win32", "darwin"] else "forkserver")
    # pre_init 是唯一被允许写配置的进程，须清掉 RestartBot 重启循环中残留的只读标记
    os.environ.pop(CONFIG_READONLY_ENV, None)
    p = mp.Process(target=func, daemon=True)
    p.start()

    while True:
        if not p.is_alive():
            break
        time.sleep(1)
    # Process.close() 之后再访问 exitcode 会抛 ValueError，故须在 terminate_process 之前取值
    exitcode = p.exitcode
    terminate_process(p)
    if exitcode != 0:
        Logger.critical(f"Pre-init failed with exit code {exitcode}, aborting.")
        sys.exit(exitcode)
```

并在 `bot.py` 顶部的 import 区（第 25 行 `from core.database import close_db` 之后）加上：

```python
from core.config import CONFIG_READONLY_ENV
```

- [ ] **Step 4: 让 bot 与 server 子进程只读**

`bot.py` 的 `run_bot()`，把

```python
async def run_bot():
    from core.config import CFGManager
    from core.server.run import run_async as server_run_async

    mp = multiprocessing.get_context("spawn" if sys.platform in ["win32", "darwin"] else "forkserver")
```

改为

```python
async def run_bot():
    from core.config import CFGManager
    from core.server.run import run_async as server_run_async

    # 自此起 spawn 出的子进程一律只读：配置的生成已在 pre_init 中完成。
    # 须在任何 mp.Process 之前置位，spawn 会继承环境；restart_bot_process() 后续重启子进程时同样受用。
    os.environ[CONFIG_READONLY_ENV] = "1"

    mp = multiprocessing.get_context("spawn" if sys.platform in ["win32", "darwin"] else "forkserver")
```

- [ ] **Step 5: 跑 lint**

```bash
./.venv/Scripts/ruff.exe format . && ./.venv/Scripts/ruff.exe check .
```

Expected: `All checks passed!`

- [ ] **Step 6: 人工验证只读确实生效**

`bot.py` 无法在测试中导入（顶层带解释器版本检查与日志器配置），改以手工方式核对环境变量这条链路：

```bash
PYTHONIOENCODING=UTF-8 AKARI_CONFIG_READONLY=1 ./.venv/Scripts/python.exe -c "
from core.config import CFGManager, CONFIG_READONLY
import sys
print('CONFIG_READONLY =', CONFIG_READONLY)
print('CFGManager.readonly =', CFGManager.readonly)
print('core.config.update 是否被导入 =', 'core.config.update' in sys.modules)
from core.config.base import CoreConfig
print('模板可读，debug =', CoreConfig.debug)
try:
    CFGManager.save()
    print('save() 未被拦截 —— 不符合预期')
except Exception as e:
    print('save() 被拦截:', type(e).__name__)
"
```

Expected:
```
CONFIG_READONLY = True
CFGManager.readonly = True
core.config.update 是否被导入 = False
模板可读，debug = <当前配置里的值>
save() 被拦截: ConfigOperationError
```

再不带环境变量跑一次，确认 `CONFIG_READONLY = False`、`core.config.update 是否被导入 = True`、`save()` 未被拦截。

- [ ] **Step 7: 确认配置目录未被改动**

```bash
git status --short config/ 2>/dev/null; ls config/*.toml | wc -l
```

Expected: `config/` 不在 git 跟踪范围内则无输出；文件数与改动前一致。若 Step 6 的验证意外写入了内容，说明只读闸门有漏。

---

## Task 6: 全量验证与文档

**Files:**
- Modify: `.claude/skills/akaribot-dev/SKILL.md`（§5.7 配置系统）

**Interfaces:**
- Consumes: 前五个任务的全部产出
- Produces: 无

- [ ] **Step 1: 跑全量测试**

```bash
CI=1 PYTHONIOENCODING=UTF-8 ./.venv/Scripts/python.exe tester.py > /tmp/final.log 2>&1; echo "EXIT=$?"
```

- [ ] **Step 2: 与基线做差集比对**

```bash
PYTHONIOENCODING=UTF-8 ./.venv/Scripts/python.exe -c "
import xml.etree.ElementTree as ET
base = {'test_arcaea','test_mcmod','test_tweet_not_found','test_wiki_headers_manage','test_wiki_not_found',
        'test_wiki_page_info','test_wiki_prefix_manage','test_wiki_search','test_locale_set','test_version_sys',
        'test_emojimix','test_idlist','test_idlist_not_found','test_nbnhhsh','test_nbnhhsh_not_found',
        'test_minecraft_news','test_dice_complex','test_hash_md5','test_hash_sha256','test_tos'}
r = ET.parse('junit.xml').getroot()
now = {tc.get('name') for tc in r.iter('testcase') if any(c.tag in ('failure','error') for c in tc)}
print('新增失败:', sorted(now - base - {'test_mcserver'}) or '无')
print('当前失败数:', len(now))
"
```

Expected: `新增失败: 无`。`test_mcserver` 打真实网络，出现即忽略。

- [ ] **Step 3: 更新开发手册**

`.claude/skills/akaribot-dev/SKILL.md` 的 §5.7，在「配置项只在模板里声明，取值处直读类属性」小节之后插入：

```markdown
#### 配置的生成只发生在 pre_init

`bot.py` 的 `pre_init()` 会调用 `core.config.scan.scan_config_templates()` 导入全部配置模板、补全缺失的键，任一模板加载失败即中止启动。此后守护进程置位环境变量 `AKARI_CONFIG_READONLY=1` 再 spawn 子进程，**bot 与 server 子进程一律只读**：

| 方法 | 只读进程中的行为 |
|---|---|
| `CFGManager.write()` / `delete()` / `save()` | 抛 `ConfigOperationError` |
| `CFGManager.get()` 读到缺失的键 | 经 `write()` 回写默认值时抛错；无默认值时返回 `None` 不抛 |
| `CFGManager.load()` / `watch()` | 正常，热重载不受影响 |
| 配置模板导入 | `__config_fields__` 照常登记，不补写配置文件 |

因此**新增配置项后必须重启机器人**，否则子进程读到该键时会抛 `ConfigOperationError`——这是刻意的，用来把「模板漏声明」当场暴露出来，而不是静默退化成默认值。

需要在运行期写配置的，只有交互式编辑命令与启动期的密钥自举两类，一律走授权接口：

```python
CFGManager.edit_write("jwt_secret", value, secret=True, table_name="bot_web")
CFGManager.edit_delete("some_key", "module_wiki")
```

`tests/unit/test_config_template.py` 会断言 `core/config/` 与 `core/scripts/` 之外不存在直接调用 `CFGManager.write` / `delete` / `save` 的地方。
```

- [ ] **Step 4: 复核文档与实现一致**

```bash
grep -n "AKARI_CONFIG_READONLY\|edit_write\|edit_delete\|scan_config_templates" .claude/skills/akaribot-dev/SKILL.md core/config/__init__.py core/config/scan.py bot.py
```

Expected: 文档中出现的每个符号都能在实现里找到同名定义。

---

## Self-Review

**Spec 覆盖核对：**

| Spec 小节 | 对应任务 |
|---|---|
| 1. 进程角色与开关传播 | Task 1 Step 3（常量与迁移闸门）、Task 5 Step 1/3/4（`bot.py` 接线） |
| 2. 只读的执行点 | Task 1 Step 4/5（守卫）、Task 2（模板导入跳过补写） |
| 3. 授权写入 | Task 1 Step 6（`edit_*`）、Task 4（调用点改造） |
| 4. pre_init 的模板扫描 | Task 3（`scan.py`）、Task 5 Step 2（接入 `pre_init`） |
| 5. pre_init 失败的传播 | Task 5 Step 3 |
| 6. 测试 | Task 1 Step 1、Task 2 Step 1、Task 3 Step 1、Task 4 Step 1 |
| 「不做的事」三条 | 计划中确无涉及 `config_generate.py` 结构、`update.py` 内部、`Bind.Module.config()` 的步骤 |

Spec 第 6 节列出的九条测试用例，八条落在 Task 1 与 Task 2；「只读下 `watch()`」一条并入 `_test_readonly_load_still_works`——`watch()` 检测到 mtime 变化后调用的正是 `load()`，二者是同一条读路径，单独再测一遍并不增加覆盖。

**与 spec 的一处偏差：** spec 第 4 节只提到 `scan_config_templates()` 一个函数，计划把「发现模板」拆成了 `iter_config_template_modules()`。原因是测试进程里模板模块已被缓存，`importlib.import_module()` 不会重新执行 `_process_class()`，「扫描补全了缺键」这件事在测试环境中无法断言；拆出纯逻辑的发现函数后，「有没有模板被静默跳过」这条最要紧的不变量才测得住。函数行为与 spec 描述一致，只是切分更细。

**类型与命名一致性核对：**

- `CONFIG_READONLY_ENV`（str）、`CONFIG_READONLY`（bool）、`CFGManager.readonly`（bool）、`CFGManager._allow_write_depth`（int）在 Task 1 定义，Task 2 用 `CFGManager.readonly`、Task 5 用 `CONFIG_READONLY_ENV`，名称一致。
- `scan_config_templates() -> list[str]` 在 Task 3 定义，Task 5 Step 2 以 `failed_templates = scan_config_templates()` 消费，返回类型一致。
- `edit_write` / `edit_delete` 在 Task 1 定义，Task 4 消费，参数顺序与 `write` / `delete` 保持一致。
- `_ensure_writable(q, table_name, secret)` 三处调用的实参顺序：`save()` 无参、`delete()` 传 `(q, table_name)`、`write()` 传 `(q, table_name, secret)`，与签名的默认值安排相符。
