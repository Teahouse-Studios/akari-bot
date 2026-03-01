"""
会话功能特性模块 - 定义消息会话支持的各种功能。

该模块通过 Features 类声明了消息会话可能支持的所有功能类型，
作为一个功能矩阵来标记特定平台或会话的能力。
"""


class Features:
    """
    会话功能特性类。

    定义了消息会话可能支持的所有功能标志位，每个属性代表一种功能。
    具体的实现会话应根据其平台能力设置这些标志位为 True 或 False。
    """

    # 图像消息支持 - 会话是否支持发送和接收图片消息
    image: bool = False

    # 语音消息支持 - 会话是否支持发送和接收语音消息
    voice: bool = False

    # 提及功能支持 - 会话是否支持 @ 提及功能（如 `@<用户名>`）
    mention: bool = False

    # 嵌入式内容支持 - 会话是否支持发送嵌入式内容（如卡片、富文本）
    embed: bool = False

    # 消息转发支持 - 会话是否支持转发消息功能
    forward: bool = False

    # 消息删除支持 - 会话是否支持删除已发送的消息
    delete: bool = False

    # 权限管理支持 - 会话是否支持权限管理功能（如禁言、踢出）
    manage: bool = False

    # Markdown 语法支持 - 会话是否支持 Markdown 格式化文本
    markdown: bool = False

    # 消息反应支持 - 会话是否支持对消息添加反应（如表情符号）
    reaction: bool = False

    # 消息引用支持 - 会话是否支持引用 / 回复消息功能
    quote: bool = False

    # RSS 推送支持 - 会话是否支持接收 RSS 推送通知
    rss: bool = False

    # 输入状态显示支持 - 会话是否支持显示“正在输入……”的状态
    typing: bool = False

    # 等待响应支持 - 会话是否支持等待用户回复的机制
    wait: bool = False
