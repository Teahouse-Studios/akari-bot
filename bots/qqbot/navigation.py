from botpy.configuration import Menu, Panel

PANEL_SCOPES = ("c2c", "group", "channel", "dm")


# C2C 输入框上菜单
# 最多 10 组，按钮最多 10 字符（5 汉字）
# 子菜单最多 5 命令，命令名称 14 字符（7 汉字）

MENU_GROUPS = (
    (
        "开始",
        (
            ("帮助", "help"),
            ("设置", "setup list"),
            ("运行状态", "ping"),
            ("关于我们", "about"),
        ),
    ),
    (
        "设置",
        (
            ("用户设置", "setup list sender"),
            ("场景设置", "setup list target"),
            ("输入提示", "setup typing"),
            ("错字纠正", "setup check"),
            ("Markdown", "setup markdown"),
        ),
    ),
    (
        "账号",
        (
            ("身份信息", "whoami"),
            ("语言设置", "locale"),
            ("前缀列表", "prefix list"),
            ("别名列表", "alias list"),
            ("账号绑定信息", "bind self"),
        ),
    ),
)

# 斜杠命令面板
# 支持 20 个命令槽位，命令名称 14 字符（7 汉字），简介 30 字符（15 汉字）
PANEL_COMMANDS = (
    ("help", "查看命令帮助"),
    ("ping", "查看机器人状态"),
    ("whoami", "查看当前身份"),
    ("bugtracker", "查询 Mojira 工单"),
    ("color", "查询或随机生成颜色"),
    ("wiki", "查询 Wiki 页面"),
    ("mcserver", "查询 Minecraft 服务器"),
    ("mcplayer", "查询 Minecraft 玩家"),
    ("nintendo-err", "查询任天堂错误码"),
    ("maimai", "使用舞萌 DX 功能"),
    ("chunithm", "使用中二节奏功能"),
    ("cytoid", "使用 Cytoid 功能"),
    ("24", "开始 24 点游戏"),
    ("cc", "开始元素符号猜谜"),
    ("coin", "抛一枚硬币"),
    ("dice", "掷一个骰子"),
    ("wordle", "开始 Wordle 游戏"),
    ("emojimix", "合成两个 Emoji"),
    ("wa", "使用 Wolfram Alpha 查询"),
    ("hitokoto", "获取随机一言"),
)

PANEL_GROUPS = (("base", PANEL_COMMANDS),)


def build_navigation() -> tuple[Menu, tuple[Panel, ...]]:
    """构造 QQ 平台的静态全局菜单与指令面板。"""
    menu = Menu(
        items=[
            Menu.submenu(
                group_name,
                [Menu.sub.message(item_name, f"/{command}") for item_name, command in items],
            )
            for group_name, items in MENU_GROUPS
        ]
    )
    panels = tuple(
        Panel(
            f"akari-static-{scope}" + (f"-{group_key}" if group_key else ""),
            scope=scope,
            items=[Panel.command(command, desc=description) for command, description in commands],
        )
        for scope in PANEL_SCOPES
        for group_key, commands in PANEL_GROUPS
    )
    return menu, panels


__all__ = [
    "MENU_GROUPS",
    "PANEL_COMMANDS",
    "PANEL_GROUPS",
    "PANEL_SCOPES",
    "build_navigation",
]
