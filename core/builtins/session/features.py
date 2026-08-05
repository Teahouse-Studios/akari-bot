"""
会话功能特性模块 - 定义消息会话支持的各种功能。

该模块通过 Features 类声明了消息会话可能支持的所有功能类型，
作为一个功能矩阵来标记特定平台或会话的能力。
"""

from attrs import define


@define
class Features:
    """
    会话功能特性类。

    定义了消息会话可能支持的所有功能标志位，每个属性代表一种功能。

    平台须以关键字参数构造本类的实例来声明自身能力，**不要以子类化的方式覆盖默认值**：
    attrs 只把带类型注解的名字视作字段，子类中漏写注解的同名属性不但不会成为字段，
    还会在 ``slots`` 重建类时被一并删除，其取值就此静默丢失，读到的仍是基类默认值。
    改用实例后，参数名由 attrs 生成的 ``__init__`` 校验，写错即报 TypeError。

    需要在既有能力集上微调时用 ``attrs.evolve()``；标志位一律在本类中声明，此处即唯一定义处。
    """

    # 图像消息支持 - 会话是否支持发送和接收图片消息
    support_image: bool = False

    # 语音消息支持 - 会话是否支持发送和接收语音消息
    support_voice: bool = False

    # 提及功能支持 - 会话是否支持 @ 提及功能（如 `@<用户名>`）
    support_mention: bool = False

    # 嵌入式内容支持 - 会话是否支持发送嵌入式内容（如卡片、富文本）
    support_embed: bool = False

    # 消息转发支持 - 会话是否支持转发消息功能
    support_forward: bool = False

    # 消息删除支持 - 会话是否支持删除已发送的消息
    support_delete: bool = False

    # 权限管理支持 - 会话是否支持权限管理功能（如禁言、踢出）
    support_manage: bool = False

    # Markdown 语法支持 - 会话是否支持 Markdown 格式化文本
    support_markdown: bool = False

    # Markdown 表格支持 - 会话是否支持以管道语法渲染表格
    support_markdown_table: bool = False

    # 消息反应支持 - 会话是否支持对消息添加反应（如表情符号）
    support_reaction: bool = False

    # 消息引用支持 - 会话是否支持引用 / 回复消息功能
    support_quote: bool = False

    # RSS 推送支持 - 会话是否支持接收 RSS 推送通知
    support_rss: bool = False

    # 输入状态显示支持 - 会话是否支持显示“正在输入……”的状态
    support_typing: bool = False

    # 等待响应支持 - 会话是否支持等待用户回复的机制
    support_wait: bool = False

    # 处理消息节点支持 - 会话是否有独立处理消息节点的能力
    support_handle_message_nodes: bool = False

    # 私聊消息支持 - 会话是否支持向指定用户单独发送私聊消息
    support_private_msg: bool = False

    # 指令操作支持 - 会话是否支持在消息中嵌入可点击的指令标签，点击后文本填入输入框
    support_action_text: bool = False

    # 按钮支持 - 会话是否支持在消息下方附带可点击的按钮
    support_button: bool = False

    # markdown 开关支持 - 平台是否允许用户自行关闭 markdown 消息
    support_markdown_toggle: bool = False

    # URL Markdown 格式支持 - 是否将 URL 自动转换为 Markdown 格式的链接
    use_url_md_format: bool = False

    # URL 跳板支持 - 是否将 URL 转为跳板链接
    use_url_manager: bool = False

    # 运行时提及支持 - 是否在命令运行时提及状态
    use_running_mention: bool = True

    # 消息过滤支持 - 是否需要将消息内容进行敏感词过滤
    require_check_dirty_words: bool = False

    # 是否需要启用模块功能 - 是否需要在场景中启用模块才可使用功能
    require_enable_modules: bool = True

    # 全部消息读取权限 - 机器人是否有权限读取场景内的全部消息，而非仅提及自身的消息
    read_all_messages: bool = True

    @classmethod
    def override(cls, **kwargs) -> "Features":
        """
        创建一个新的 Features 实例，并根据提供的关键字参数覆盖默认值。

        例如：
            features = Features.override(support_image=True, support_mention=True)
            这将创建一个 Features 实例，其中 support_image 与 support_mention 被启用（True），
            其他功能保持默认值。

        等价于直接构造实例，保留本方法仅为兼容既有调用点。原实现以 ``hasattr`` 筛选关键字，
        名称有误时静默跳过；改为转调构造函数后，由 attrs 生成的 ``__init__`` 抛出 TypeError。
        """
        return cls(**kwargs)
