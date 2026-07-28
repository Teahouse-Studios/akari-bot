# 配置生成的进程隔离

## 背景

配置文件目前会被多个进程反复触发生成。三条路径：

1. **子进程重新执行 `bot.py` 顶层代码。** `multiprocessing` 以 spawn（Windows / macOS）或 forkserver（Linux）启动子进程时，会把主模块以 `__mp_main__` 重新导入一遍。于是每个 bot 子进程与 server 子进程都会再跑一次 `bot.py` 第 7 行的 `config_generate` 存在性检查与第 26 行的 `from core.config.base import CoreConfig`，后者触发 `_process_class.__generate_config_file()` 补写缺失键。
2. **配置版本迁移在导入期执行。** `core/config/update.py` 第 49、137、254 行是顶层 `if`，而 `core/config/__init__.py` 第 23 行无条件导入它。任何进程只要导入 `core.config` 就会跑一次迁移。
3. **运行期的隐式回写。** `CFGManager.get()` 读到缺失的键时调用 `write()` 持久化默认值；配置模板类属性的读取全部经由 `get()`，因此每个子进程在运行中都可能写盘。

叠加 `CFGManager` 的进程间锁（`.config.lock`），多个进程并发补写同一批键既拖慢启动，也让「配置项由谁写入」变得不可追溯。

## 目标

配置的**生成**收敛到 `bot.py` 的 `pre_init()` 一处；bot 与 server 子进程默认只读，仅通过一组显式的授权接口供 `modules/core/su_utils.py` 的交互式编辑命令写入。

## 设计

### 1. 进程角色与开关传播

新增环境变量 `AKARI_CONFIG_READONLY`。`core/config/__init__.py` 在模块顶部读取一次，落为 `CFGManager.readonly` 类属性。

选择环境变量而非其它机制，是因为闸门必须赶在 `core.config` 被导入之前生效，而另外两个候选都做不到：

- **`Info` 类上加标志**（现有 `Info.subprocess` 的路子）：`go()` 中 `Info.subprocess = True` 之前的 `from core.logger import Logger` 已经把 `core.config` 连同 `core.config.update` 拉起来了。
- **`multiprocessing` 传参给 target 函数**：spawn 先把主模块以 `__mp_main__` 重新导入，`bot.py` 第 26 行在 target 函数被调用之前就执行了。

| 进程 | 可写 | 机制 |
|---|---|---|
| 守护进程（`bot.py` `__main__`） | 可写但不写 | 把第 26 行的 `from core.config.base import CoreConfig` 挪进 `pre_init()`（仅第 93、117 行用到），守护进程顶层不再触碰配置模板 |
| `pre_init` 子进程 | 可写 | spawn 前 `os.environ.pop("AKARI_CONFIG_READONLY", None)`，覆盖 `RestartBot` 重启循环中的残留 |
| bot 子进程 | 只读 | `run_bot()` spawn 前 `os.environ["AKARI_CONFIG_READONLY"] = "1"` |
| server 子进程 | 只读 | 同上 |
| `tester.py` / `core/scripts/config_generate.py` / 其它脚本 | 可写 | 环境变量不存在，默认可写 |

默认可写而非默认只读：测试框架与配置生成脚本都不经过 `bot.py`，默认只读会把它们一并锁死。

配置版本迁移的闸门装在导入处，不改 `update.py` 自身。注意 `import core.config.update` 位于 `core/config/__init__.py` 第 23 行，而 `class CFGManager` 从第 33 行才开始，闸门处取不到类属性，因此环境变量须先落为模块级常量：

```python
# core/config/__init__.py，置于 import core.config.update 之前
CONFIG_READONLY = bool(os.environ.get("AKARI_CONFIG_READONLY"))

if not CONFIG_READONLY:
    import core.config.update  # noqa

...

class CFGManager:
    readonly: bool = CONFIG_READONLY
```

`core.config.update` 全仓仅此一处导入，且是纯副作用导入，无需暴露任何名字。

模块级常量只用于决定「本进程启动时是否执行版本迁移」，此后一切运行期判断都读 `CFGManager.readonly`。测试改类属性即可，不会（也不应）回溯影响已经完成的迁移导入。

### 2. 只读的执行点

闸门装在 `CFGManager` 的三个持久化入口，而非最底层的 `_atomic_write()`——后者拦截时 `cls.values` 已被修改，内存与磁盘会分叉。

| 方法 | 只读时的行为 |
|---|---|
| `write()` | 在修改 `cls.values` 之前抛 `ConfigOperationError` |
| `delete()` | 同上 |
| `save()` | 抛 `ConfigOperationError` |
| `load()` / `watch()` / `get()` / `switch_config_path()` | 不拦截。只读进程仍需读取，也仍需靠 mtime 检测热重载 |

三处的判据统一为 `if cls.readonly and not cls._allow_write_depth: raise ConfigOperationError(...)`，须早于 `cls._exclusive()` 加锁与任何状态改动。

在 `write()` 中该判据置于 `if value is None: ... return` 之后而非方法体最前——无默认值的读取（如 `Config("default_locale", cfg_type=str)`）会以 `value=None` 走到这里并提前返回，本就不写盘，不应抛错。`delete()` 与 `save()` 则置于方法体最前。

`get()` 不直接拦截，但它读到缺失的键时会经 `write()` 回写默认值，于是在那里撞上闸门抛错——模板漏声明的键因此当场暴露。`get()` 在无默认值时（如 `Config("default_locale", cfg_type=str)`）`write()` 会提前返回而不写盘，这类调用在只读进程中是安全的。

`_process_class.__generate_config_file()` 在只读进程中整段跳过，`__config_fields__` 的登记照常进行——模板类属性可读，只是不再补写配置文件。

异常消息须带上键名、表名与进程名，形如：

```
Config is read-only in this process, cannot write "qq_typing_emoji" to table "bot_onebot".
Missing keys must be generated in pre_init.
```

### 3. 授权写入

```python
class CFGManager:
    readonly: bool = bool(os.environ.get("AKARI_CONFIG_READONLY"))
    _allow_write_depth: int = 0

    @classmethod
    @contextmanager
    def _writable(cls):
        """临时解除只读，仅供 edit_* 使用。可重入。"""
        cls._allow_write_depth += 1
        try:
            yield
        finally:
            cls._allow_write_depth -= 1

    @classmethod
    def edit_write(cls, q, value, cfg_type=None, secret=False, table_name=None):
        """供交互式编辑命令使用的授权写入。"""
        with cls._writable():
            cls.write(q, value, cfg_type, secret, table_name)

    @classmethod
    def edit_delete(cls, q, table_name=None) -> bool:
        """供交互式编辑命令使用的授权删除。"""
        with cls._writable():
            return cls.delete(q, table_name)
```

用深度计数而非布尔标志：`write()` 内部会调用 `save()`，两层都须放行；将来若出现嵌套调用也不会提前解锁。

命名为 `edit_*` 而非给 `write()` 加 `force` 参数，是为了让 `grep edit_` 能穷举全部合法写入点，同时避免他人看到只读报错后随手加个 `force=True` 绕过。

调用点改动：

| 位置 | 改动 |
|---|---|
| `modules/core/su_utils.py` 的 `~config write` | `CFGManager.write` → `CFGManager.edit_write` |
| `modules/core/su_utils.py` 的 `~config delete` | `CFGManager.delete` → `CFGManager.edit_delete` |
| `modules/core/su_utils.py` 的 `~config get` | 不改。不传默认值，不会触发写盘 |
| `bots/web/client.py` 的 jwt_secret 自举 | `CFGManager.write` → `CFGManager.edit_write` |

### 4. pre_init 的模板扫描

`pre_init()` 中新增一步，排在清理 cache 之后、数据库迁移之前：

实现落在新文件 `core/config/scan.py`，`bot.py` 的 `pre_init()` 调用它并按返回值决定是否中止。把逻辑放在可导入的模块里而非 `bot.py` 内部，是为了让它能被单元测试直接调用——`bot.py` 顶层带有解释器版本检查、日志器配置等副作用，测试中不宜导入。

```python
# core/config/scan.py
def scan_config_templates() -> list[str]:
    """导入全部配置模板，补全配置文件中缺失的键。

    :return: 加载失败的配置模板模块名列表，空列表表示全部成功。
    """
    import bots
    import modules
    import core.config.base  # noqa: F401  核心配置模板

    failed = []
    for package in (bots, modules):
        package_path = Path(package.__path__[0])
        for submodule in pkgutil.iter_modules(package.__path__):
            if not (package_path / submodule.name / "config.py").exists():
                continue  # 该 bot 或模块没有配置模板
            module_name = f"{package.__name__}.{submodule.name}.config"
            try:
                importlib.import_module(module_name)
            except Exception:
                failed.append(module_name)
                logger.exception(f"[Config] Failed to load config template {module_name}: ")
    CFGManager.save()
    return failed
```

**「有没有模板」用文件是否存在判断，而不是捕获 `ModuleNotFoundError`。** 后者分不清两种情况：该 bot / 模块本就没有 `config.py`，与模板自身 import 了一个不存在的依赖。第二种会被静默跳过，正是本设计要杜绝的漏键。现有 `core/scripts/config_generate.py` 就有这个问题，本次不改它（属另一条链路），但新代码不沿用。

同理不用 `importlib.util.find_spec(f"modules.{name}.config")` 做判断——它会为了拿到 `__path__` 而导入父包 `modules.<name>`，把整个模块包及其依赖全拉起来，正好抵消模板作为叶子模块带来的好处。

**模板是叶子模块，这一步才成立。** 前一轮改造把 `modules/*/config.py` 从 `from . import dice` + `@dice.config()` 改为 `@on_module_config("dice")`，因此 `importlib.import_module("modules.dice.config")` 只加载模板本身，不会连带拉起整个模块包及其依赖。

**扫描不看启用状态。** 无论 bot 的 `enable` 是否为 false、模块是否被禁用，配置键一律补全，否则用户先禁用再启用就会撞上缺键。与现有 `config_generate.py` 的行为一致。

**模板导入失败即拒绝启动。** `pre_init()` 拿到非空的 `failed` 后 `Logger.critical` 列出全部失败项并 `sys.exit(1)`。缺失的键会在子进程读取时抛错，与其让机器人跑起来之后某条命令莫名失败，不如在启动阶段停下并列出坏掉的模板。

`bot.py` 第 7~8 行首次运行时的 `import core.scripts.config_generate` 保持不动——它仅在 `config.toml` 不存在时触发，子进程启动时该文件必然已存在。

### 5. pre_init 失败的传播

现有的 `multiprocess_run_until_complete()` 只等待子进程结束便调用 `terminate_process(p)`，`p.exitcode` 未被检查，`sys.exit(1)` 会被静默吞掉。改为：

```python
def multiprocess_run_until_complete(func):
    mp = multiprocessing.get_context("spawn" if sys.platform in ["win32", "darwin"] else "forkserver")
    p = mp.Process(target=func, daemon=True)
    p.start()

    while p.is_alive():
        time.sleep(1)
    exitcode = p.exitcode  # 须在 terminate_process 之前取，Process.close() 之后访问会抛 ValueError
    terminate_process(p)
    if exitcode != 0:
        Logger.critical(f"Pre-init failed with exit code {exitcode}, aborting.")
        sys.exit(exitcode)
```

### 6. 测试

新增 `tests/unit/test_config_readonly.py`，用 `CFGManager.switch_config_path()` 切到临时目录，不触碰真实的 `config/`。只读标志落为 `CFGManager.readonly` 类属性而非模块级常量，测试可直接改类属性。

| 用例 | 断言 |
|---|---|
| 只读下 `write()` | 抛 `ConfigOperationError`，且 `CFGManager.values` 未被修改 |
| 只读下 `delete()` | 抛 `ConfigOperationError` |
| 只读下 `save()` | 抛 `ConfigOperationError` |
| 只读下 `get()` 读缺失键（带默认值） | 抛 `ConfigOperationError` |
| 只读下 `get()` 读缺失键（无默认值） | 返回 `None`，不抛 |
| 只读下 `load()` / `watch()` | 正常，能读到磁盘上的新值 |
| `edit_write()` / `edit_delete()` | 只读下仍成功写盘 |
| `_writable()` 退出后 | 恢复只读，再次 `write()` 仍抛 |
| 只读下导入配置模板 | `__config_fields__` 完整，且未产生文件写入 |

前一轮新增的 `tests/unit/test_config_template.py` 中「模板取值与配置文件一致」一条会调用 `CFGManager.get()`，在只读默认关闭的情况下不受影响。

## 不做的事

- 不改 `core/scripts/config_generate.py`。它生成的是 `assets/config_store/` 下的分发用配置，与运行期的 `config/` 是两条独立链路。
- 不改 `core/config/update.py` 的内部结构。闸门装在其唯一的导入处。
- 不动 `Bind.Module.config()`。它已标记弃用，保留供向后兼容。
