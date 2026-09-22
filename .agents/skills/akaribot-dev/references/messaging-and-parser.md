# 消息、会话与命令解析

## 目录

- [Bot 类](#51-bot-类-corebuiltinsbot__init__py)
- [消息系统](#52-消息系统-corebuiltinsmessage)
- [会话系统](#53-会话系统-corebuiltinssession)
- [命令解析器](#54-命令解析器-corebuiltinsparser)
- [parser 入口 hook](#parser-入口-hook-corebuiltinsparserhooks)
- [KE 码](#122-ke-码消息元素文本表示)
- [上下文保持](#123-上下文保持长任务)
- [执行锁](#124-执行锁防并发)
- [TOS 与错字纠正](#125-tos-限流)
- [自定义异常](#128-自定义异常)

这是当前最大的一份参考文件。只修改 loader、配置、数据库或队列时不要读取它；对应内容在 `infrastructure.md`。只修改模块声明和业务命令时先读 `module-development.md`，仅在涉及消息、会话或 parser API 时再加载本文件。

---

### 5.1 Bot 类 (`core/builtins/bot/__init__.py`)

中央枢纽类，大多数需要类状态的方法为 `@classmethod`；纯转发方法也可能是 `@staticmethod`：

```python
class Bot:
    # 类型/工具引用（供模块使用，避免模块再去 import 深层路径）
    MessageSession = MessageSession
    FetchedMessageSession = FetchedMessageSession
    ModuleHookContext = ModuleHookContext
    ExecutionLockList = ExecutionLockList
    Info = Info
    Temp = Temp
    PrivateData = PrivateData

    # 上下文管理
    ContextSlots: list[ContextManager] = []  # 已注册的平台上下文管理器
    fetched_session_ctx_slot = 0             # fetch_target 用的 slot
    base_superuser_list = CoreConfig.base_superuser

    # 核心方法（除特别标注外为 @classmethod）
    async def process_message(cls, session_info, ctx, features_override=None)
    # 消息入口 - 接收平台消息，注入 Features，发送到 JobQueue

    async def post_message(cls, module_name, message, ...)
    # 主动发送消息到启用了指定模块的所有会话
    @staticmethod
    async def post_global_message(message, ...)
    # 主动发送消息到所有会话（不限模块）

    async def fetch_target(cls, target_id, sender_id=None, create=False)
    async def fetch_target_list(cls, target_list, create=False) -> list[FetchedSessionInfo]
    async def get_enabled_this_module(cls, module) -> list[FetchedSessionInfo]
    async def send_direct_message(cls, session_info, message, ...)

    async def start_typing(cls, session_info) -> None
    async def end_typing(cls, session_info) -> None

    def register_context_manager(cls, ctx_manager, fetch_session=False) -> int
    # 注册平台上下文管理器，返回 slot 索引
    def register_bot(cls, client_name=None, private_data_path=None)
    # 不传 private_data_path 时落在 data/private/<client_name 小写>/

    # camelCase 别名
    postMessage = post_message
    postGlobalMessage = post_global_message

    class Hook:
        @staticmethod
        async def trigger(module_or_hook_name, session_info=None, args=None)
        # 触发模块钩子
```

**导出机制**：`Bot` 通过 `core/exports.py` 的 `add_export(Bot)` 注册到全局 `exports` 对象，其他模块通过 `from core.exports import exports; Bot = exports["Bot"]` 访问，避免循环导入。需要修改注册、加载时机或导出机制时，同时读取主技能直接链接的 `infrastructure.md`。

### 5.2 消息系统 (`core/builtins/message/`)

#### MessageChain (`chain.py`)

```python
@define
class MessageChain:
    values: list[MessageElement]  # 消息元素列表

    @classmethod
    def create(cls)               # 空链
    @classmethod
    def assign(cls, elements)     # 工厂方法，支持 str/list/dict/None
    @classmethod
    def from_list(cls, lst)       # 从 to_list() 的结果还原

    def as_sendable(self, session_info) -> list  # 转换为可发送格式
    def to_str(self) -> str       # 转换为纯文本
    def to_list(self) -> list[dict]              # 序列化（跨进程用）
    def to_kecode(self) -> str                   # 转 KE 码
    @property
    def is_safe(self) -> bool     # 安全检查（敏感信息过滤）

    # 列表式操作
    def append(self, element)
    def remove(self, element)
    def insert(self, index, element)
    def extend(self, other)
    def copy(self)
    def contains(self, types) -> bool   # 是否含指定元素类型
    def only(self, types) -> bool       # 是否只含指定元素类型
```

支持 `+`、`+=`、`in`、迭代、`len()`、`str()` 操作。

#### 消息元素 (`elements.py`, `internal.py`)

```python
# elements.py - 基类
class BaseElement:
    def kecode(self) -> str       # KE 码表示

# 具体元素（字段以真实定义为准）
@define
class PlainElement(BaseElement):
    text: str
    disable_joke: bool = False        # 跳过愚人节文本替换

@define
class MarkdownElement(PlainElement):  # 注意：继承自 PlainElement
    ...

@define
class ImageElement(BaseElement):
    path: str                          # 本地路径、URL 或 base64
    headers: dict[str, Any] | None = None
    need_get: bool = False             # 是否需要先下载

@define
class AudioElement(BaseElement):
    path: str

@define
class VideoElement(BaseElement):
    path: str

@define
class URLElement(BaseElement):
    url: str
    applied_mm: bool | None = None     # 链接跳板
    applied_md_format: bool = False    # Markdown 格式
    md_format_name: str | None = None  # Markdown 显示名

@define
class FormattedTimeElement(BaseElement):
    timestamp: float
    date: bool = True
    iso: bool = False
    time: bool = True
    seconds: bool = True
    timezone: bool = True

@define
class EmbedFieldElement(BaseElement):
    name: str
    value: str
    inline: bool = False

@define
class EmbedElement(BaseElement):
    title: str | None = None
    description: str | None = None
    url: str | None = None
    timestamp: float = ...
    color: int = 0x0091FF
    image: ImageElement | None = None
    thumbnail: ImageElement | None = None
    author: str | None = None
    footer: str | None = None
    fields: list[EmbedFieldElement] | None = None

@define
class MentionElement(BaseElement):
    client: str                        # 注意：是 client + id 两个字段
    id: str

@define
class I18NContextElement(BaseElement):
    key: str
    kwargs: dict[str, Any]             # 模板参数
    fallback: bool = True
    locale_failed_prompt: bool = True
    disable_joke: bool = False

@define
class RawElement(BaseElement):
    value: str                         # 原样透传给平台

@define
class ActionTextElement(BaseElement):
    ...                                # 可点击执行的命令文本，平台需 support_action_text

@define
class ButtonElement(BaseElement):
    ...                                # 按钮，平台需 support_button

@define
class ButtonFrameElement(BaseElement):
    ...                                # 按钮容器
```

> 元素类的完整字段以 `core/builtins/message/elements.py` 的定义为准；上表只列出改动时最常碰到的那些。

```python
# internal.py - 便捷别名。注意这些是 .assign 工厂方法，不是类本身
Plain = plain = PlainElement.assign
Markdown = markdown = MarkdownElement.assign
Image = image = ImageElement.assign
Audio = audio = AudioElement.assign
Video = video = VideoElement.assign
Embed = embed = EmbedElement.assign
EmbedField = embed_field = EmbedFieldElement.assign
Url = url = URLElement.assign
FormattedTime = formatted_time = FormattedTimeElement.assign
I18NContext = i18n_context = I18NContextElement.assign
Mention = mention = MentionElement.assign
Raw = raw = RawElement.assign
ActionText = action_text = ActionTextElement.assign
Button = button = ButtonElement.assign
ButtonFrame = button_frame = ButtonFrameElement.assign
```

> **重要**：`Plain` 等名字绑定的是 `XxxElement.assign` 这个 classmethod，**不是类**。所以 `isinstance(x, Plain)` 会直接报错，类型判断必须用 `elements.py` 里的真实类（`PlainElement` 等）。`assign` 会做参数归一化（例如 `I18NContext("key", a=1)` 把 `a=1` 收进 `kwargs` 字段），因此构造消息元素一律走别名，不要直接调类构造器。

#### 消息链类型优先级

```
PlatformMessageChain > I18NMessageChain > MessageChain
```

平台特定消息链可以覆盖默认行为。

### 5.3 会话系统 (`core/builtins/session/`)

#### SessionInfo (`info.py`)

```python
@define
class SessionInfo:
    # 基本信息（只有前三个是必需的）
    target_id: str                    # 目标 ID（如 "QQ|Group|123456"）
    target_from: str                  # 平台来源（如 "QQ", "Discord"）
    client_name: str                  # 客户端名称
    sender_id: str | None = None
    sender_from: str | None = None
    sender_name: str | None = None

    # 消息信息
    message_id: str | None = None
    reply_id: str | None = None
    messages: MessageChain | None = None
    timestamp: float | None = None
    session_id: str | None = None     # 由 assign() 生成

    # 平台能力标志（由 Features 注入）
    superuser: bool = False
    support_image / support_audio / support_video / support_mention / support_embed
    support_delete / support_manage / support_permission_group
    support_markdown / support_markdown_extension
    support_reaction / support_quote / support_rss / support_typing
    support_wait / support_handle_message_nodes / support_private_msg
    support_action_text / support_button / support_markdown_toggle     # 均默认 False

    # 数据库模型（挂的是 union 行，不是平台 ID 行）
    target_union_info: TargetUnionInfo | None = None
    sender_union_info: SenderUnionInfo | None = None
    target_union_id: str | None = None
    sender_union_id: str | None = None
    target_channel_id: int = 1        # 本会话在场景组内的消息通道号

    # 权限与配置
    banned_users: list | None = None
    custom_admins: list | None = None
    locale: Locale | None = None      # 注意是 Locale 对象，不是 str
    timezone_offset: timedelta | None = None
    bot_name / bot_id: str | None = None
    muted: bool | None = None
    enabled_modules: list | None = None
    petal: int | None = None
    prefixes: list[str] = []          # 默认空列表，实际前缀由 parser 从配置/数据库合并
    next_hops: list[str] = []         # 主动推送失败时的下一跳场景
    ctx_slot: int | None = 0          # 指向 Bot.ContextSlots 的索引
    fetch: bool = False
    is_private: bool = False           # 由平台适配器显式判定

    # 行为开关（由 Features 注入）
    require_enable_modules: bool = True
    read_all_messages: bool = True
    require_check_dirty_words: bool = False
    use_url_manager: bool = False
    use_url_md_format: bool = False
    use_running_mention: bool = True
    tmp: dict[str, str] | None = {}   # 单次处理内的临时数据

    @classmethod
    async def assign(cls, target_id, sender_id, ...) -> "SessionInfo"
    # 异步工厂方法 - 从数据库加载信息
    async def refresh_info(self)      # 重新拉取数据库状态
```

#### MessageSession (`internal.py`)

传给模块处理函数的主要对象：

```python
@define
class MessageSession:
    session_info: SessionInfo           # 一切状态的入口
    sent: list[MessageChain] = []       # 已发送消息
    trigger_msg: str = ""               # 触发消息文本
    matched_msg: Match | None = None    # 正则匹配结果
    parsed_msg: dict = {}               # 解析后的参数

    @property
    def target(self) -> SessionInfo     # ⚠️ 已废弃，等价于 session_info，新代码不要用

    @classmethod
    async def from_session_info(cls, session: SessionInfo)

    # 发送消息
    async def send_message(self, message_chain, quote=True, ...) -> FinishedSession
    async def finish(self, message_chain=None, ...) -> NoReturn  # 发送并抛 SessionFinished
    async def send_direct_message(self, message_chain, ...)
    async def send_private_message(self, message_chain, user_id=None, ...) -> list[str]
    # 私信给某个用户（默认是本会话的用户），消息不进当前场景；
    # 返回空列表即发送失败（平台不支持私信、未加好友、对方关了私信……），
    # 需要私密投递的内容（如绑定码）据此判定成败，不要假定一定送达

    # 等待用户交互
    async def wait_confirm(self, message_chain=None, ...) -> bool
    async def wait_next_message(self, message_chain=None, ...) -> MessageSession | None
    async def wait_reply(self, message_chain, ...) -> MessageSession | None
    async def wait_anyone(self, message_chain=None, ...) -> MessageSession | None
    async def sleep(self, s: float)     # 会顺带 hold 上下文的 sleep

    # 权限检查
    def check_super_user(self) -> bool          # 同步
    async def check_permission(self) -> bool    # ⚠️ 是 async，必须 await
    async def check_native_permission(self) -> bool

    # 消息转换 / 格式化
    def as_display(self, text_only=False) -> str
    def format_time(self, ...) -> str           # 按会话时区/语言格式化时间
    def format_num(self, number, precision=0) -> str  # 按语言习惯格式化数字

    # 平台操作（通过 JobQueue 回到 bot 进程）
    async def delete(self, reason=None)         # ⚠️ 删除的是本条消息，无 message_id 参数
    async def restrict_member(self, user_id, duration=None, reason=None)
    async def unrestrict_member(self, user_id)
    async def kick_member(self, user_id, reason=None)
    async def ban_member(self, user_id, reason=None)
    async def unban_member(self, user_id)
    async def add_reaction(self, emoji)         # ⚠️ 只接 emoji，作用于本条消息
    async def remove_reaction(self, emoji)
    async def handle_error_signal(self)
    async def hold(self) / async def release(self)      # 长任务保持上下文
    async def start_typing(self) / async def end_typing(self)

    # 平台原生 API 直通
    async def call_api(self, api_name, **kwargs)
    async def call_onebot_api(self, api_name, **kwargs)
```

**`FinishedSession`**: `send_message()` 的返回值，包含 `message_id` 和 `delete()` 方法。
**`FetchedMessageSession`**: `MessageSession` 的子类，由 `Bot.fetch_target()` 产出，用于主动发消息（没有真实触发消息）。

#### ContextManager (`context.py`)

平台适配器必须实现的抽象基类：

```python
class ContextManager(ABC):
    context: dict[str, Any] = {}  # session_id -> 平台上下文
    features: Features = Features()

    # 上下文生命周期
    @classmethod
    def add_context(cls, session_info, context)
    @classmethod
    def del_context(cls, session_info)
    @classmethod
    def hold_context(cls, session_info)   # 防止删除（长任务）
    @classmethod
    def release_context(cls, session_info) # 释放保持

    # 派生一份指向私聊场景的 SessionInfo（换掉 target、清掉 session_id / message_id），
    # 各平台的 send_private_msg 靠它复用自家的 send_message，不必重写一遍渲染逻辑
    @classmethod
    def derive_private_session(cls, session_info, target_id, target_from) -> SessionInfo

    # 平台必须实现的 17 个抽象方法（全部是 @classmethod + @abstractmethod）
    async def check_native_permission(cls, session_info) -> bool
    async def check_bot_state(cls, session_info) -> BotState
    async def send_message(cls, session_info, message, ...) -> list[str]
    async def send_private_msg(cls, session_info, user_id, message, ...) -> list[str]
    # 私信给 user_id（带平台前缀），session_info 只提供语言与能力上下文；
    # 实现必须吞掉平台异常并返回 []，调用方以"有没有拿到消息 ID"判定成败
    async def delete_message(cls, session_info, message_id, ...) -> None
    async def restrict_member(cls, session_info, user_id, duration, ...) -> None
    async def unrestrict_member(cls, session_info, user_id) -> None
    async def kick_member(cls, session_info, user_id, reason=None) -> None
    async def ban_member(cls, session_info, user_id, reason=None) -> None
    async def unban_member(cls, session_info, user_id) -> None
    async def grant_permission_group(cls, session_info, ...) -> None
    async def revoke_permission_group(cls, session_info, ...) -> None
    async def add_reaction(cls, session_info, message_id, emoji) -> None
    async def remove_reaction(cls, session_info, message_id, emoji) -> None
    async def start_typing(cls, session_info) -> None
    async def end_typing(cls, session_info) -> None
    async def error_signal(cls, session_info) -> None
```

平台不支持某个能力时，实现里直接 `pass`（或抛 `NotImplementedError`）并在 `Features` 里把对应 `support_*` 置 `False`；框架靠 `Features` 决定是否调用，而不是靠捕获异常。

#### Features (`features.py`)

平台能力声明。`Bot.process_message()` 会把这些字段注入到 `SessionInfo` 的同名字段上。

```python
@define
class Features:
    # 消息能力
    support_image: bool = False
    support_audio: bool = False
    support_video: bool = False
    support_mention: bool = False
    support_embed: bool = False
    support_delete: bool = False
    support_manage: bool = False
    support_permission_group: bool = False
    support_markdown: bool = False
    support_markdown_extension: bool = False
    support_reaction: bool = False
    support_quote: bool = False
    support_rss: bool = False
    support_typing: bool = False
    support_wait: bool = False
    support_handle_message_nodes: bool = False
    support_private_msg: bool = False
    support_action_text: bool = False
    support_button: bool = False
    support_markdown_toggle: bool = False

    # 行为开关
    use_url_md_format: bool = False
    use_url_manager: bool = False
    use_running_mention: bool = True       # 注意默认是 True
    require_check_dirty_words: bool = False
    require_enable_modules: bool = True    # 注意默认是 True
    read_all_messages: bool = True         # 是否可读取场景内全部消息

    @classmethod
    def override(cls, **kwargs) -> Features
    # 构造一份 Features 实例；需要基于既有实例微调时使用 attrs.evolve()
```

平台必须用关键字参数构造 `Features` **实例**，不要通过子类覆盖默认值，也不要把 `Features` 类本身赋给 ContextManager。

### 5.4 命令解析器 (`core/builtins/parser/`)

#### 模板语法 (`args.py`)

```
<arg>              # 必需参数
[flag <arg>]       # 可选参数（带标志）
{description}      # 描述文本（不参与解析）
...                # 变长参数
{{I18N:key}}       # i18n 描述（双花括号）
```

示例：

```python
"echo <text>"                    # 必需参数
"search <query> [-l <lang>]"     # 可选参数
"choice <items> ..."             # 变长参数
"hello {{I18N:module.help}}"     # i18n 描述
```

#### parser() 主函数 (`core/builtins/parser/message.py`)

消息处理核心流程：

```python
async def parser(msg: MessageSession):
    # 0. 刷新会话信息，并分发 SESSION_READY 入站策略
    await msg.session_info.refresh_info()

    # 1. 分发 SESSION_BEFORE_WAIT 后检查任务队列
    await SessionTaskManager.check(msg)

    # 2. 取该平台/客户端可用的模块，把消息转成可读文本
    modules = ModulesManager.return_modules_list(target_from, client_name)
    msg.trigger_msg = normalize_space(msg.as_display())
    await dispatch_parser_hook(HookPoint.MESSAGE_NORMALIZED, msg)
    if not msg.trigger_msg: return

    # 3. 命令前缀匹配
    if in_prefix_list or disable_prefix:
        # 命令解析 → CHANNEL_CLAIM → 模块匹配 → 执行
        command_first_word = await _process_command(msg, modules, ...)
        if command_first_word in modules:
            await _execute_module(msg, modules, command_first_word, ...)
        else:
            # 未命中：分发 COMMAND_UNMATCHED，由订阅方提出 RecoveryProposal
            await _try_command_recovery(msg, modules, command_first_word, ...)
    else:
        # 正则匹配
        await _execute_regex(msg, modules, ...)
```

#### parser 入口 hook (`core/builtins/parser/hooks/`)

parser 主干只保留解析与派发，**策略行为一律挂在 `HookPoint` 上**（`points.py` 定义点位，`dispatch.py` / `executor.py` 负责分发与超时收尾）。订阅实现集中在 `modules/core/hooks/`：

| 文件 | 负责 |
| --- | --- |
| `policies.py` | 各点位的默认策略（含未命中时的语法与"模块不存在"提示） |
| `tos.py` | TOS 限流与封禁（见 §12.5） |
| `typo.py` | rapidfuzz 错字纠正（见 §12.6） |
| `routing.py` | `CHANNEL_CLAIM` 频道去重 |
| `errors.py` / `telemetry.py` / `retired.py` | 错误上报、统计、退役客户端迁移 |

订阅方通过返回 `results.py` 里的结果类型决定 parser 后续走向：`Continue`（放行）、`RewriteTrigger`（改写触发文本）、`Stop`（按 `StopScope` 中止）、`Handled`（已自行处理，不再走默认提示）、`RecoveryProposal`（提出纠正建议）。**改解析期行为前先判断它归属主干还是某个订阅**——直接在 `message.py` 里加分支往往是改错了地方。

`_try_command_recovery()` 拿到 `RecoveryProposal` 后会 `wait_confirm` 问用户，确认期间模块可能被热重载或停用，因此会用 `use_cache=False` 重取模块表并经 `_validate_recovery_target()` 复核后才执行。

#### 消息通道 (message channel)

一个现实中的群里可能同时蹲着好几个小可（比如 OneBot 与 QQ 官方 bot 各一个），它们各自收到同一条消息。
`TargetUnionBind.channel_id` 用来表达这件事：**同一个场景组内 `channel_id` 相同的场景 = 现实中的同一个场景**。

- 编号在组内从 1 开始逐个递增（`TargetUnionBind.next_channel_id()`），**默认各占一号，也就是默认谁也不跟谁去重**。
  取用当前会话的通道号直接读 `session_info.target_channel_id`，不要去翻模型内部。
- 用户侧由 `~bind channel` 一组命令管理，`~bind channel auto` 会让两个小可用一对口令互认，
  自动合并场景组并统一通道号。
- **命令去重**：`modules/core/hooks/routing.py` 订阅 `CHANNEL_CLAIM`，以模块 runtime 状态做抢占式认领。
  跨平台的消息 ID 无法互通，判定「同一条消息」靠「纯文本 hash 一致 + 收到时间相差不超过
  `CHANNEL_DEDUP_WINDOW`（10 秒）」。查表与写入之间不能有 `await`，靠单线程事件循环保证原子性。
- **推送去重**：见下面的「主动推送流程」。
- 另有 `target_data["bots_id"]` 记录彼此的机器人账号，用于屏蔽对方发的消息——那是另一件事，别和去重混为一谈。

> ⚠️ 测试环境**不走这个 `parser()`**，走的是 `core/tester/mock/parser.py` 的简化版。诊断测试与生产差异时，同时读取主技能直接链接的 `testing.md`。


---

### 12.2 KE 码（消息元素文本表示）

格式为 `[KE:type,param1=value1,param2=value2]`：

```
[KE:plain,text=Hello World]
[KE:image,path=https://example.com/img.png]
[KE:voice,path=/path/to/audio.ogg]
[KE:i18n,i18nkey=my_module.message.hello,name=World]
[KE:mention,userid=QQ|123456789]
```

用于日志、模板字符串、跨进程传递。`MessageChain.to_kecode()` 生成，`MessageChain.assign()` 能反向解析混排文本（`"Hello [KE:plain,text=World] !"` → 三个块）。

### 12.3 上下文保持（长任务）

平台上下文（SDK 的 event 对象等）默认在一轮消息处理结束后被清掉。长任务需要显式保持，否则后续 `send_message` 会找不到上下文。

模块里用 `MessageSession` 的方法（跨进程走 JobQueue）：

```python
await msg.hold()
# ... 长时间运行的任务 ...
await msg.release()
```

适配器进程内部则直接操作 `ContextManager`：

```python
ctx_manager.hold_context(session_info)
ctx_manager.release_context(session_info)
```

`msg.sleep(s)` 内部已经处理了保持，长等待优先用它。

### 12.4 执行锁（防并发）

```python
# 自动管理，同一用户的命令串行执行。锁的粒度是 sender_id（不是 target_id）
class ExecutionLockList:
    _list = set()  # 存储正在执行的 sender_id

    @staticmethod
    def add(msg)            # 加锁
    @staticmethod
    def remove(msg)         # 解锁
    @staticmethod
    def check(msg) -> bool  # 检查是否锁定
    @staticmethod
    def get() -> set        # 取全部锁定用户（调试用）
```

也可通过 `Bot.ExecutionLockList` 访问。锁是**进程内内存**，server 进程崩溃重启后自动清空。

### 12.5 TOS 限流

`modules/core/hooks/tos.py` 订阅 parser 入口 hook，用令牌桶双层限流：

- 命令级：同一条命令 `TokenBucket(10, 300)` —— 10 次/300 秒
- 全局级：所有命令 `TokenBucket(20, 300)` —— 20 次/300 秒

任一桶耗尽即抛 `AbuseWarning`。后续处理同在该文件：累计警告数达到 `tos_warning_counts`（默认 5）后临时封禁 `tos_temp_ban_time` 秒（默认 300），并上报管理员。整套机制由 `enable_tos` 配置开关控制，超级用户豁免。

另有一套独立的**群组手动冷却**（`cooldown_time`，存在 `TargetUnionInfo.target_data` 里），管理员豁免。

### 12.6 错字纠正

`modules/core/hooks/typo.py` 订阅 `COMMAND_UNMATCHED`，用 `rapidfuzz` 逐层模糊匹配：模块名 → 命令 → 选项 → 参数。它不直接发消息，而是返回 `RecoveryProposal`，由 parser 的 `_try_command_recovery()` 用 `wait_confirm` 问用户「你是不是想输入 xxx」。

阈值全部在 `core/config/core.py` 的 `CoreConfig` 里声明（默认值如下）：

| 配置项 | 默认 | 作用 |
|--------|------|------|
| `typo_check_module_score` | `0.6` | 模块名相似度下限 |
| `typo_check_command_score` | `0.3` | 命令相似度下限 |
| `typo_check_options_score` | `0.3` | 选项相似度下限 |
| `typo_check_args_score` | `0.5` | 参数相似度下限 |
| `typo_check_module_diff_ratio` | `0.5` | 模块名**长度比**下限 |
| `typo_check_args_diff_ratio` | `0.5` | 参数**数量比**下限 |

长度比那两项是为了挡住「短输入误匹配到长命令」（源码注释举的例子是 `~p` → `~decrypt`）：`min_len / max_len < ratio` 就丢弃这个匹配。

用户可以在自己的 `sender_data` 里把 `typo_check` 设成 `False` 关掉这个功能。


---

### 12.8 自定义异常

定义在 `core/constants/exceptions.py`，共 15 个。**注意前三个继承的是 `BaseException` 而不是 `Exception`** —— 它们是控制流信号，不能被业务代码里的 `except Exception` 吞掉：

```python
class SendMessageFailed(BaseException):   """发送消息失败"""
class SessionFinished(BaseException):     """会话完成，终止处理（msg.finish() 抛出）"""
class WaitCancelException(BaseException): """等待被用户取消"""
```

其余 12 个继承 `Exception`（`SessionContextUnavailable` 继承 `ValueError`）：

| 异常                       | 含义                     |
| -------------------------- | ------------------------ |
| `AbuseWarning`             | 滥用警告（触发 TOS 处理）|
| `ConfigFileNotFound`       | 配置文件不存在           |
| `ConfigOperationError`     | 配置操作失败             |
| `ConfigValueError`         | 配置值非法               |
| `ExternalException`        | 外部服务异常             |
| `InvalidCommandFormatError`| 命令格式非法             |
| `InvalidHelpDocTypeError`  | 帮助文档类型非法         |
| `SessionContextUnavailable`| 会话上下文已失效         |
| `InvalidTemplatePattern`   | 命令模板语法非法         |
| `NoReportException`        | 不上报的异常             |
| `QueueAlreadyRunning`      | 队列已在运行             |
| `TestException`            | 测试专用                 |

> 在模块里 `try` 包裹含 `await msg.finish()` 的代码时，用 `except Exception` 是安全的（`SessionFinished` 不会被捕获）；但如果写了 `except BaseException` 或裸 `except:`，命令会卡住不返回。

---

