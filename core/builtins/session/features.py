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
    具体的实现会话应根据其平台能力设置这些标志位为 True 或 False。
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

    # URL Markdown 格式支持 - 是否将 URL 自动转换为 Markdown 格式的链接
    use_url_md_format: bool = False

    # URL 跳板支持 - 是否将 URL 转为跳板链接
    use_url_manager: bool = False

    # 运行时提及支持 - 是否在命令运行时提及状态
    use_running_mention: bool = True

    # 消息过滤支持 - 是否需要将消息内容进行敏感词过滤
    require_check_dirty_words: bool = False

    # 是否需要启用模块功能 - 是否需要在会话中启用模块才可使用功能
    require_enable_modules: bool = False

    @classmethod
    def override(cls, **kwargs):
        """
        创建一个新的 Features 实例，并根据提供的关键字参数覆盖默认值。

        例如：
            features = await Features.override(image=True, mention=True)
            这将创建一个 Features 实例，其中 image 和 mention 功能被启用（True），其他功能保持默认值（False）。
        """
        instance = cls()
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance
