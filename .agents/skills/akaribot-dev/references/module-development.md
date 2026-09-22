# 模块开发

## 目录

- [核心原则](#核心原则)
- [常见任务速查](#11-常见开发任务速查)
- [基本结构与最小示例](#71-基本结构)
- [命令、正则与权限](#73-命令模板详解)
- [配置与数据库](#76-模块配置)
- [定时任务与钩子](#78-定时任务)
- [国际化](#710-国际化i18n)
- [主动消息与状态系统](#711-主动发送消息)
- [等待用户交互](#715-等待用户交互)

修改模块配置或数据库模型时，同时读取主技能直接链接的 `infrastructure.md`。修改 `MessageSession`、消息元素或 parser 行为时，同时读取 `messaging-and-parser.md`。测试规则只以 `testing.md` 为准。

---


---

## 11. 常见开发任务速查

### 创建新模块

1. 在 `modules/` 下创建目录
2. 创建 `__init__.py`，使用 `module()` 注册
3. 添加命令、正则、定时任务
4. 可选：创建 `config.py`、`database/models.py`；有任何面向用户的文本时必须创建 `locales/zh_cn.json`，不要编辑其他语言文件

### 添加新命令

```python
@my_mod.command("command_name <arg> {{I18N:my_module.help.text}}")
async def _(msg: Bot.MessageSession, arg: str):
    await msg.finish(I18NContext("my_module.message.result", arg=arg))
```

同时在 `modules/my_module/locales/zh_cn.json` 补上 `my_module.help.text` 和 `my_module.message.result` 两个键。

### 热重载模块

```python
status, reload_count = await ModulesManager.reload_module("module_name")
```

或通过命令：`~module reload <module> ...`（需超级用户）。注意重载是**按 Python 文件**而不是按模块名进行的 —— 同一个 `.py` 里定义的其他模块会被一起重载，`reload_count` 就是实际重载的模块数。

### 修改配置

直接编辑 `config/*.toml` 即可，**不需要任何重载命令**：配置读取会触发 `CFGManager.watch()`；它按短时间间隔扫描 mtime，发现变动就自动 `load()`，因此修改可能延迟至多一个 watch 间隔生效。

---


---

## 7. 模块开发指南

### 核心原则

> **国际化优先**: 模块内默认**不编写纯文本消息**，所有面向用户的文本必须使用 `I18NContext` 组件进行国际化。编写代码时只在对应模块目录下的 `locales/zh_cn.json` 添加或修改本地化节点；简体中文是基础语言。
>
> 例外情况：仅在调试日志、内部逻辑字符串等不面向用户的场景可使用纯文本。
>
> **翻译文件归属**：除非用户明确要求处理翻译或 Weblate 同步结果，否则**禁止创建、修改、删除或机械同步 `core/**/locales/`、`bots/**/locales/`、`modules/**/locales/` 中 `zh_cn.json` 以外的语言 JSON**，包括 `en_us.json`、`zh_tw.json`、`ja_jp.json`、`ko_kr.json` 等。其他语言由 Weblate 及其 bot 自动提交；即使现有翻译缺少新键，也只更新 `zh_cn.json`，不要复制简体中文或自行翻译补齐。`assets/config_store/<语言>/` 属于配置模板派生物，不在这条 Weblate 规则内；非 `zh_cn` 版本也不要手改，应交给配置生成自动化。

### 7.1 基本结构

```
modules/my_module/
├── __init__.py          # 模块入口，导出命令
├── commands.py          # 命令实现（可选，可直接写在 __init__.py）
├── config.py            # 模块配置（可选）
├── database/
│   └── models.py        # 数据库模型（可选）
├── locales/             # 国际化文件（必需）
│   ├── zh_cn.json       # 简体中文（基础语言，由代码贡献者维护）
│   └── ...              # 其他语言由 Weblate bot 维护，不要手动改动
└── utils/               # 工具函数（可选）
```

### 7.2 最小模块示例

```python
# modules/my_module/__init__.py
from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module

my_mod = module(
    "my_module",
    alias={"mm": "my_module"},
    developers=["YourName"],
    desc="{I18N:my_module.help.desc}",
    doc=True,
)

@my_mod.command("hello {{I18N:my_module.help.hello}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(I18NContext("my_module.message.hello"))

@my_mod.command("echo <text> {{I18N:my_module.help.echo}}")
async def _(msg: Bot.MessageSession, text: str):
    await msg.finish(I18NContext("my_module.message.echo", text=text))
```

```json
// modules/my_module/locales/zh_cn.json
{
    "my_module.help.desc": "示例模块",
    "my_module.help.hello": "打个招呼",
    "my_module.help.echo": "重复你说的话",
    "my_module.message.hello": "你好，世界！",
    "my_module.message.echo": "复读：${text}"
}
```

> **注意**: 模块 `desc` 与 `options_desc` 使用 `{I18N:...}` 单花括号语法，命令模板的描述位使用 `{{I18N:...}}` 双花括号语法；代码中通过 `I18NContext(key, **kwargs)` 发送国际化消息。消息参数使用 `string.Template` 格式的 `${param_name}` 占位符传入，不是 `{param_name}`。

### 7.3 命令模板详解

```python
# 基本命令
@my_mod.command("hello")
async def _(msg): ...

# 带必需参数
@my_mod.command("echo <text>")
async def _(msg, text: str): ...

# 带可选参数
@my_mod.command("search <query> [-l <lang>]")
async def _(msg, query: str):
    lang = msg.parsed_msg.get("-l", {}).get("<lang>")
    # parsed_msg = {"<query>": "...", "-l": {"<lang>": "..."}}

# 变长参数
@my_mod.command("choice <items> ...")
async def _(msg):
    items = [msg.parsed_msg.get("<items>")] + msg.parsed_msg.get("...", [])

# 无参数命令（默认处理）
@my_mod.command()
async def _(msg): ...

# 多个命令模板（同一个函数）——传列表，这是项目里的主流写法
@my_mod.command([
    "add <alias> <command> {{I18N:my_module.help.add}}",
    "remove <alias> {{I18N:my_module.help.remove}}",
])
async def _(msg): ...

# i18n 描述（双花括号）
@my_mod.command("hello {{I18N:my_module.help.hello}}")

# 带选项描述（options_desc 的值用单花括号 {I18N:...}）
@my_mod.command(
    "search <query> [-l <lang>] {{I18N:my_module.help.search}}",
    options_desc={"-l": "{I18N:my_module.help.option.l}"},
)
```

#### 参数是怎么注入到函数里的

`core/builtins/parser/message.py` 的 `_build_command_kwargs()` 做的是**基于签名的注入**，规则要点：

```python
@bilibili.command("<bid> [-i] {{I18N:...}}", options_desc={"-i": "{I18N:...}"})
async def _(msg: Bot.MessageSession, bid: str, get_detail=False):
    ...
```

| 情况 | 行为 |
|------|------|
| 函数只有 **1 个参数** | 无视注解，直接把 `msg` 传进去 |
| 函数有 **多个参数** | 逐个按名字去 `parsed_msg` 里找 |
| 参数注解为 `Bot.MessageSession` | 收到 `msg` |
| 参数名 `foo` | 先找 `parsed_msg["<foo>"]`，再找 `parsed_msg["foo"]` |
| 注解为 `int` / `float` / `bool` | 自动转换；转换失败抛 `InvalidCommandFormatError` |
| 找不到对应值 | 用函数默认值；没默认值就传 `None` |
| 注解为 `Param("<名字>", 类型)` | 显式指定要取哪个 key（参数名和模板名不一致时用） |

> ⚠️ **`MessageSession` 参数必须注解成 `Bot.MessageSession`**。框架是按 `param_obj.annotation == bot.MessageSession` 判定的，直接 `from core.builtins.session.internal import MessageSession` 再拿它当注解**不生效**——日志里会打 `has no Bot.MessageSession parameter, did you forgot to add it?`，运行时行为也会错乱。源码里的原话就是「Remember: MessageSession IS NOT Bot.MessageSession」。
>
> 另：注入只在 `parsed_msg` 非空时发生。裸 `@my_mod.command()`（无模板）的函数只能有一个参数。

`Param` 用法（`core/types/command/__init__.py`）：

```python
@echo.command("<display_msg>")
async def _(msg: Bot.MessageSession, dis: Param("<display_msg>", str)):
    ...
```

### 7.4 正则匹配

```python
@my_mod.regex(r"正则模式", mode="M", desc="{I18N:my_module.help.regex}")
async def _(msg: Bot.MessageSession):
    # msg.matched_msg 包含匹配结果
    await msg.finish(I18NContext("my_module.message.matched"))
```

完整签名：

```python
def regex(self, pattern, mode="M", flags=re.NOFLAG, desc=None,
          required_admin=False, required_superuser=False, required_base_superuser=False,
          available_for="*", exclude_from="", load=True,
          logging=True,        # 是否记录日志
          show_typing=True,    # 是否显示"正在输入"，同时决定是否走 TOS 计数
          text_only=True,      # 是否只对纯文本消息生效
          element_filter=None) # 只在消息含指定元素类型时触发
```

mode 参数（**默认为 `"M"`**）：

| 值                | 行为                                            |
| ----------------- | ----------------------------------------------- |
| `"M"` / `"MATCH"` | `re.match`，`msg.matched_msg` 是 `Match` 对象   |
| `"A"` / `"FINDALL"` | `re.findall`，`msg.matched_msg` 是列表        |

大小写不敏感（内部 `mode.upper()`）。

### 7.5 权限控制

```python
# 模块级别
my_mod = module("my_module", required_admin=True)      # 需要管理员
my_mod = module("my_module", required_superuser=True)   # 需要超级用户

# 命令级别
@my_mod.command("set <sides>", required_admin=True)
async def _(msg, sides: int): ...

# 运行时检查
@my_mod.command("dangerous")
async def _(msg):
    if not msg.check_super_user():                 # 同步
        await msg.finish(I18NContext("my_module.error.permission"))
    if not await msg.check_permission():           # ⚠️ async，必须 await
        await msg.finish(I18NContext("my_module.error.permission"))
```

`check_permission()` 覆盖群组管理员 / 自定义管理员 / 超级用户三类；`check_native_permission()` 才是问平台要原生权限。`msg.finish()` 会抛 `SessionFinished`，所以后面不需要 `return`。

### 7.6 模块配置

配置写在 `modules/<模块名>/config.py` 里，由加载器自动 import（见 §5.5）。`on_module_config(module_name, secret=False)` 把类里的**带类型注解的字段 + 默认值**写进配置文件的 `module_<模块名>` 表。

```python
# modules/ai/config.py —— 真实例子
from core.config.decorator import on_module_config

@on_module_config("ai")
class AiConfig:
    ai_default_llm: str = ""
    llm_timeout: float = 60
    llm_max_tokens: int = 2048

@on_module_config("ai", secret=True)   # 敏感配置写进 module_ai_secret 表
class AiConfigSecret:
    e2b_api_key: str = ""
```

读取直接取类属性，键名、默认值、类型、表名都不必重写：

```python
from modules.ai.config import AiConfig, AiConfigSecret

timeout = AiConfig.llm_timeout
api_key = AiConfigSecret.e2b_api_key
```

- 模板类**不依赖模块对象**，因而是叶子模块，同包内任何文件都可以在顶层导入它；用 `Bind.Module.config()` 声明会因 `from . import <模块变量>` 造成循环导入
- 传给 `on_module_config()` 的模块名通常须与 `module()` 声明的一致；模块主名为连字符、下划线形式作为命令别名保留时，配置表名可沿用下划线形式。其它不一致会被 `tests/unit/test_config_template.py` 拦下
- 配置类**不会被实例化**，只是当作声明式 schema 用；不要在里面写方法或 `__init__`
- 默认值决定类型校验，所以 `llm_timeout: float = 60` 这种要注意别写成 `int`

### 7.7 数据库模型

模块模型放在 `modules/<模块名>/database/models.py`。`core/database/__init__.py:34` 的 `fetch_module_db()` 会用 `pkgutil.iter_modules(modules.__path__)` 遍历所有模块，尝试 `find_spec("modules.<name>.database.models")`——**存在即自动注册到 Tortoise 的 `models` app，不需要手动登记**；找不到就静默跳过。

表名约定：模块内定义 `table_prefix = "module_<模块名>_"`，各表用 f-string 拼。

```python
# modules/cytoid/database/models.py —— 真实例子
from tortoise import fields

from core.database.base import DBModel
from core.database.models import UNION_SCOPE_SENDER

table_prefix = "module_cytoid_"


class CytoidBindInfo(DBModel):
    """
    Cytoid 用户绑定信息。

    :param union_id: 绑定的用户联合 ID。
    :param username: 绑定的用户名。
    """

    union_scope = UNION_SCOPE_SENDER
    union_id = fields.CharField(max_length=512, primary_key=True)
    username = fields.CharField(max_length=512)

    class Meta:
        table = f"{table_prefix}bind_info"

    @classmethod
    async def set_bind_info(cls, union_id: str, username: str):
        ...
```

- 必须继承 `core.database.base.DBModel`（不是 `tortoise.Model`），它提供 `get_by_target_id` 等便利方法
- 会话归属数据用 `union_id = fields.CharField(max_length=512, primary_key=True)`，并按归属声明 `union_scope = UNION_SCOPE_SENDER` 或 `UNION_SCOPE_TARGET`；不要新增 `sender_id` / `target_id` 状态列把同一用户或场景按平台割裂
- 业务逻辑习惯写成模型上的 `@classmethod`，而不是散在命令函数里
- `database/__init__.py` 可以是空文件，但**必须存在**，否则 `find_spec` 找不到

```python
from modules.my_module.database.models import MyModuleData

data = await MyModuleData.get_by_target_id(msg)
data.data["key"] = "value"
await data.save()
```

用户归属模型对应使用 `await MyModuleData.get_by_sender_id(msg)`。这两个方法会先把平台 ID 解析为 union，再按 `union_id` 查询或创建。

### 7.8 定时任务

`core/scheduler.py` 里的 `Scheduler` 是一个全局 `AsyncIOScheduler` 实例，由 server 进程启动。`@my_mod.schedule(trigger)` 接受任意 APScheduler trigger（`Interval` / `Cron` / `Date` / `And` / `Or`）。

```python
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

@my_mod.schedule(IntervalTrigger(hours=1))
async def hourly_task():
    # 每小时执行；定时任务里没有 msg，主动发消息只能走 Bot.post_message
    await Bot.post_message("my_module", I18NContext("my_module.message.hourly"))

@my_mod.schedule(CronTrigger(hour=0, minute=0))
async def daily_task():
    pass
```

定时任务函数**不接收参数**。要给用户发消息就用 `Bot.post_message(模块名, ...)`，框架会自动只发给开启了该模块的会话。

### 7.9 模块钩子

钩子用于**跨模块调用**：一个模块注册能力，另一个模块按名字触发。回调固定收一个 `Bot.ModuleHookContext`：

```python
@define
class ModuleHookContext:
    args: dict                              # 触发方传入的参数
    session_info: SessionInfo | None = None # 触发方所在会话（可能为 None）
```

```python
# 注册方（如 modules/wiki/wiki.py）
@wiki.hook("autosearch")
async def auto_search(ctx: Bot.ModuleHookContext):
    title = ctx.args["title"]
    target = await WikiTargetInfo.get_by_target_id(ctx.session_info.target_id)
    ...
    return [...]        # 返回值会回传给触发方

# 触发方
result = await Bot.Hook.trigger("wiki.autosearch", session_info, args={"title": "Foo"})
```

钩子名在注册表里是 `<模块名>.<钩子名>`，触发时要带模块名前缀。

具名 hook 与 parser 入口 hook 共享执行基础：模块加载状态、平台过滤、runtime generation、超时和取消收尾均由统一执行器处理。调用具名能力使用 `Bot.Hook.trigger("module.hook", session_info=..., args=...)`；调用模块名则按优先级广播该模块全部具名 hook，单个回调失败会记录并继续。具名 hook 的 `timeout` 默认 5 秒，传入 `timeout <= 0` 可显式取消限制。测试和计划任务应走 `core.builtins.hooks.dispatch_module_hook()`，不要直接调用注册表中的函数。

### 7.10 国际化（i18n）

#### 规则

- **所有面向用户的文本必须使用 `I18NContext`**，禁止直接使用 `Plain("纯文本")`
- **只编辑 `zh_cn.json`**；其他语言文件由 Weblate bot 维护，不得自行新增、补键、翻译或同步
- 命令模板中的描述使用 `{{I18N:key}}` 语法
- 模块 `desc` 参数使用 `{I18N:key}` 语法（单花括号）
- 参数化消息使用 `string.Template` 格式的 `${param}` 占位符

#### 语言文件格式

```json
// modules/my_module/locales/zh_cn.json
{
    "my_module.help.desc": "这是一个示例模块",
    "my_module.help.hello": "打个招呼",
    "my_module.help.echo": "重复你说的话",
    "my_module.help.option.l": "语言",
    "my_module.message.success": "操作成功！",
    "my_module.message.greeting": "你好，${name}！",
    "my_module.error.not_found": "未找到结果。",
    "my_module.error.permission": "权限不足。"
}
```

#### 命名约定

```
{module_name}.{category}.{key}

category 常用值:
  help.desc       - 模块描述
  help.xxx        - 命令帮助文本
  help.option.xxx - 选项描述
  message.xxx     - 正常输出消息
  error.xxx       - 错误消息
```

#### 代码中使用

```python
from core.builtins.message.internal import I18NContext

# 简单消息
await msg.finish(I18NContext("my_module.message.success"))

# 带参数的消息
await msg.finish(I18NContext("my_module.message.greeting", name="World"))

# 命令模板中的 i18n
@my_mod.command("hello {{I18N:my_module.help.hello}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(I18NContext("my_module.message.hello"))
```

#### 错误示例（禁止）

```python
# ❌ 错误：使用纯文本
await msg.finish("操作成功！")
await msg.finish(f"你好，{name}！")

# ✅ 正确：使用 I18NContext
await msg.finish(I18NContext("my_module.message.success"))
await msg.finish(I18NContext("my_module.message.greeting", name=name))
```

### 7.11 主动发送消息

```python
from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext

# 发送到所有启用了该模块的会话（session_list=None 时自动查库）
await Bot.post_message("my_module", I18NContext("my_module.message.broadcast"))

# message 传 dict 可按平台分发，"default" 为兜底
await Bot.post_message("my_module", {
    "default": I18NContext("my_module.message.broadcast"),
    "Discord": embed_chain,
})

# 发送到特定目标
target = await Bot.fetch_target("QQ|Group|123456789")   # 返回 FetchedSessionInfo | None
if target:
    await Bot.send_direct_message(target, I18NContext("my_module.message.hello"))

# 批量
targets = await Bot.fetch_target_list(["QQ|Group|1", "Discord|Channel|2"])
# 查出开启了某模块的全部会话
targets = await Bot.get_enabled_this_module("my_module")
```

`module_name` 传 `"*"` 表示全局（也可以直接用 `Bot.post_global_message()`）。

### 7.12 使用冷却系统

```python
from core.utils.cooldown import CoolDown

# CoolDown(key, msg, delay, whole_target=False)
# whole_target=True 时冷却作用于整个对话而非单个用户
cd = CoolDown("my_command", msg, delay=60)

remaining = cd.check()  # 返回剩余秒数（float），0 表示可用
if remaining > 0:
    await msg.finish(I18NContext("my_module.message.cooldown", time=int(remaining)))

# 执行命令...
cd.reset()  # 重新计时
```

### 7.13 使用花瓣系统

```python
from core.utils.petal import cost_petal, gained_petal, lost_petal, sign_get_petal

# 花费花瓣：余额不足返回 False，send_prompt=True 时自动发提示
if await cost_petal(msg, 10):
    ...  # 执行操作

# 增减花瓣，返回一个可直接拼进消息链的 I18NContextElement（或 None）
prompt = await gained_petal(msg, 5)
prompt = await lost_petal(msg, 5)
if prompt:
    await msg.finish([I18NContext("my_module.message.done"), prompt])

# 签到奖励
await sign_get_petal(msg)
```

### 7.14 使用游戏状态

`PlayState`（`../../../../core/utils/game.py`）是**实例化**使用的，按 `(target_id, game)` 两级维度隔离游戏状态，底层是 `ExpiringTempDict`，**1 小时（`GAME_EXPIRED`）自动过期**，所以卡死的对局会自愈。

```python
from core.utils.game import PlayState

play_state = PlayState("my_game", msg)  # 构造：游戏名 + 消息会话

if play_state.check():  # 该场景下这个游戏是否正在进行
    await msg.finish(I18NContext("my_module.message.playing"))

play_state.enable()  # 开局
play_state.update(answer="42", tries=0)  # 存任意局内数据
...
answer = play_state.get("answer")  # 取局内数据，可带 default
if not play_state.check():  # 每次异步等待回来都要重新确认没被中断
    return
play_state.disable()  # 结束
```

| 方法              | 作用                                       |
| ----------------- | ------------------------------------------ |
| `enable()`        | 开启游戏事件并刷新过期时间                 |
| `disable()`       | 关闭游戏事件                               |
| `check() -> bool` | 读取 `_status`，未开启/已过期返回 `False`  |
| `update(**kwargs)`| 写入局内数据                               |
| `get(key, default)`| 读取局内数据                              |

> 状态是**进程内内存**（不落库），server 进程重启即丢失。`_status` 是保留键，不要用 `update(_status=...)` 覆盖。

### 7.15 等待用户交互

四个方法都在 `core/builtins/session/internal.py`：

| 方法 | 签名要点 | 返回 |
|------|----------|------|
| `wait_confirm` | `(message_chain=None, quote=True, delete=True, timeout=120, append_instruction=True, no_confirm_action=True)` | `bool` |
| `wait_next_message` | `(message_chain=None, quote=True, delete=False, timeout=120, append_instruction=True, possibly_choices=None)` | `MessageSession` |
| `wait_reply` | `(message_chain, quote=True, delete=False, timeout=120, all_=False, append_instruction=True)` | `MessageSession` |
| `wait_anyone` | `(message_chain=None, quote=False, delete=False, timeout=120)` | `MessageSession` |

```python
# 等待确认（平台支持则用反应，否则用文本）
if await msg.wait_confirm(I18NContext("my_module.message.confirm")):
    await msg.finish(I18NContext("my_module.message.confirmed"))
else:
    await msg.finish(I18NContext("my_module.message.cancelled"))

# 等待下一条消息
next_msg = await msg.wait_next_message(I18NContext("my_module.message.ask"))
await msg.finish(I18NContext("my_module.message.echo", text=next_msg.as_display()))

# 发送并等待回复（message_chain 是必填参数）
reply = await msg.wait_reply(I18NContext("my_module.message.ask_name"), timeout=60)
await msg.finish(I18NContext("my_module.message.greeting", name=reply.as_display()))

# 等待场景内任意成员发言（多人游戏抢答用）
answer = await msg.wait_anyone(timeout=30)
```

> ⚠️ **超时不返回 `None`，而是 `raise WaitCancelException`。** 所以 `if next_msg:` 这种写法是没意义的——超时时根本走不到那一行。`WaitCancelException` 继承自 **`BaseException`**（见 §12.8），框架会在外层捕获并给用户发提示，模块里通常**不要**自己 catch。
>
> 其他共同行为：
> - 进入等待前会 `ExecutionLockList.remove(self)` + `end_typing()`，所以等待期间用户可以触发别的命令
> - `wait_confirm` 在配置 `no_confirm` 为真时**直接返回 `no_confirm_action`**（默认 `True`），不发消息也不等待——写破坏性操作时要意识到确认可能被全局跳过
> - `append_instruction=True` 会自动追加平台相关的操作提示（反应 / 回复 / 文本），一般别关
> - `message_chain` 不填就只等不发；`wait_reply` 例外，它是必填的

---

