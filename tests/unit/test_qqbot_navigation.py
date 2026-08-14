"""QQBot 静态全局菜单与指令面板测试。"""

from botpy.configuration import ConfigurationManager

from bots.qqbot.navigation import MENU_GROUPS, PANEL_GROUPS, PANEL_SCOPES, build_navigation
from core.logger import Logger
from core.tester import Tester, func_case


def _text_width(value: str) -> int:
    return sum(1 if ord(character) < 128 else 2 for character in value)


def _test_navigation_declarations() -> bool:
    menu, panels = build_navigation()
    menu_data = menu.to_dict()
    if len(menu_data["items"]) != len(MENU_GROUPS):
        Logger.error(f"Unexpected QQBot menu group count: {menu_data}")
        return False

    menu_commands = []
    for menu_item, (group_name, expected_items) in zip(menu_data["items"], MENU_GROUPS, strict=True):
        if (
            menu_item["type"] != "menu"
            or menu_item["name"] != group_name
            or len(menu_item["sub_menu_items"]) != len(expected_items)
        ):
            Logger.error(f"Unexpected QQBot menu group {group_name}: {menu_item}")
            return False
        actual_names = [item["name"] for item in menu_item["sub_menu_items"]]
        expected_names = [name for name, _ in expected_items]
        actual_commands = [item["send_message"] for item in menu_item["sub_menu_items"]]
        expected_commands = [f"/{command}" for _, command in expected_items]
        if actual_names != expected_names or actual_commands != expected_commands:
            Logger.error(f"Unexpected QQBot menu items for {group_name}: {menu_item}")
            return False
        menu_commands.extend(actual_commands)

    expected_menu_command_count = sum(len(items) for _, items in MENU_GROUPS)
    if len(menu_commands) != expected_menu_command_count or any(
        not command.startswith("/") for command in menu_commands
    ):
        Logger.error(f"QQBot menu commands must match the slash-prefixed declarations: {menu_commands}")
        return False
    if any(command.startswith(("/~", "/～", "//")) for command in menu_commands):
        Logger.error(f"QQBot menu commands must use exactly one slash prefix: {menu_commands}")
        return False

    incomplete_commands = {
        "/3dsdb",
        "/bug",
        "/github",
        "/ip",
        "/mcmod",
        "/mcplayer",
        "/mcserver",
        "/nbnhhsh",
        "/nintendo-err",
        "/random choice",
        "/random number",
        "/whois",
        "/wiki search",
    }
    if incomplete_commands.intersection(menu_commands):
        Logger.error(f"QQBot menu must not send incomplete parameter commands: {menu_commands}")
        return False

    expected_scopes = tuple(scope for scope in PANEL_SCOPES for _ in PANEL_GROUPS)
    if tuple(panel.scope for panel in panels) != expected_scopes:
        Logger.error(f"Unexpected QQBot panel scopes: {[panel.scope for panel in panels]}")
        return False
    if len({panel.key for panel in panels}) != len(PANEL_SCOPES) * len(PANEL_GROUPS):
        Logger.error(f"QQBot panel keys must be unique: {[panel.key for panel in panels]}")
        return False

    for panel, (_, commands) in zip(panels, PANEL_GROUPS * len(PANEL_SCOPES), strict=True):
        panel_data = panel.to_dict()
        actual_commands = [item["name"] for item in panel_data["items"]]
        actual_descriptions = [item["desc"] for item in panel_data["items"]]
        expected_commands = [command for command, _ in commands]
        expected_descriptions = [description for _, description in commands]
        if (
            panel.target_type != "all"
            or actual_commands != expected_commands
            or actual_descriptions != expected_descriptions
        ):
            Logger.error(f"Unexpected QQBot panel declaration for {panel.scope}: {panel_data}")
            return False
        if len(actual_commands) != 20 or len(set(actual_commands)) != 20:
            Logger.error(f"QQBot panel must contain 20 unique commands: {actual_commands}")
            return False
        if any(command.startswith(("/", "~", "～")) for command in actual_commands):
            Logger.error(f"QQBot panel commands must not carry a prefix: {actual_commands}")
            return False
        if panel_data["remark"] != f"[botpy:{panel.key}]":
            Logger.error(f"Unexpected managed marker for {panel.key}: {panel_data['remark']}")
            return False
    return True


def _test_navigation_limits() -> bool:
    menu, panels = build_navigation()
    menu_data = menu.to_dict()
    if len(menu_data["items"]) > 10 or len(panels) > 20:
        return False
    for item in menu_data["items"]:
        if _text_width(item["name"]) > 10 or len(item["sub_menu_items"]) > 5:
            return False
        for sub_item in item["sub_menu_items"]:
            if _text_width(sub_item["name"]) > 14:
                Logger.error(f"QQBot submenu label exceeds its width limit: {sub_item}")
                return False
    for panel in panels:
        panel_items = panel.to_dict()["items"]
        if len(panel_items) > 20 or any(_text_width(item["name"]) > 14 for item in panel_items):
            return False
        if any(_text_width(item.get("desc", "")) > 30 for item in panel_items):
            return False
    return True


class _FakeAPI:
    def __init__(self):
        self.calls = []
        self.panel_id = 0

    async def get_menu(self):
        self.calls.append(("get_menu",))
        return {"menu": None, "version": 0}

    async def update_menu(self, menu):
        self.calls.append(("update_menu", menu))
        return {"version": 1}

    async def get_panels(self, scope, *, cursor=None, limit=20):
        self.calls.append(("get_panels", scope, cursor, limit))
        return {"records": [], "next_cursor": "", "is_end": True}

    async def create_panel(self, scope, panel, **kwargs):
        self.panel_id += 1
        self.calls.append(("create_panel", scope, panel, kwargs))
        return {"panel_id": f"panel-{self.panel_id}"}


async def _test_navigation_sync() -> bool:
    menu, panels = build_navigation()
    api = _FakeAPI()
    result = await ConfigurationManager(api, menu=menu, panels=panels).sync()
    if not result.menu_changed or result.panels_created != len(panels) or result.panels_updated != 0:
        Logger.error(f"Unexpected QQBot configuration sync result: {result}")
        return False
    queried_scopes = tuple(call[1] for call in api.calls if call[0] == "get_panels")
    created_scopes = tuple(call[1] for call in api.calls if call[0] == "create_panel")
    expected_created_scopes = tuple(scope for scope in PANEL_SCOPES for _ in PANEL_GROUPS)
    if queried_scopes != PANEL_SCOPES or created_scopes != expected_created_scopes:
        Logger.error(f"Unexpected QQBot panel sync calls: {api.calls}")
        return False
    return any(call[0] == "update_menu" for call in api.calls)


@func_case
async def test_qqbot_navigation(tester: Tester):
    """bots.qqbot.navigation: 静态菜单与指令面板测试"""
    await tester.test(_test_navigation_declarations, "静态导航声明测试")
    await tester.test(_test_navigation_limits, "平台容量与文本限制测试")
    await tester.test(_test_navigation_sync, "SDK 声明式同步测试")
    return tester
