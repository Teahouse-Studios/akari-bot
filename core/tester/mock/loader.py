import importlib
import pkgutil

from core.constants import lang_list, all_locales_path
from core.i18n import build_locale_snapshot, connect_locale_snapshot
from core.loader import ModulesManager
from core.logger import Logger


def apply_monkey_patch(module, monkey_patches: dict[str, object] | None):
    if not monkey_patches:
        return

    for name, mock_obj in monkey_patches.items():
        if hasattr(module, name):
            setattr(module, name, mock_obj)


async def load_modules(show_logs=True, monkey_patches: dict[str, object] | None = None, load_fixtures: bool = True):
    import modules

    # 测试显式配置默认 RPC peer，与生产入口一致，避免依赖模块导入顺序。
    from core.queue.server import JobQueueServer
    from core.queue.rpc import set_default_peer

    set_default_peer(JobQueueServer)

    err_prompt = []
    locale_loaded_err = build_locale_snapshot(list(lang_list.keys()), all_locales_path, "akari-bot")
    if locale_loaded_err:
        err_prompt.append("I18N loaded failed:")
        err_prompt.append("\n".join(locale_loaded_err))
    connect_locale_snapshot("akari-bot")

    # Load HTTP fixtures if available
    if load_fixtures:
        try:
            from core.tester.mock.fixtures import load_http_fixtures

            count = load_http_fixtures()
            if count > 0 and show_logs:
                Logger.info(f"Loaded {count} HTTP fixtures.")
        except Exception:
            if show_logs:
                Logger.exception("Failed to load HTTP fixtures:")

        try:
            from core.tester.mock.webrender import load_webrender_fixtures

            count = load_webrender_fixtures()
            if count > 0 and show_logs:
                Logger.info(f"Loaded {count} WebRender fixtures.")
        except Exception:
            if show_logs:
                Logger.exception("Failed to load WebRender fixtures:")

    if show_logs:
        Logger.info("Attempting to load modules...")

    for subm in pkgutil.iter_modules(modules.__path__):
        module_py_name = f"{modules.__name__}.{subm.name}"

        try:
            if show_logs:
                Logger.debug(f"Loading {module_py_name}...")

            module = importlib.import_module(module_py_name)
            apply_monkey_patch(module, monkey_patches)

            if show_logs:
                Logger.debug(f"Successfully loaded {module_py_name}!")

            try:
                importlib.import_module(f"{module_py_name}.config")
                if show_logs:
                    Logger.debug(f"Successfully loaded {module_py_name}'s config definition!")
            except ModuleNotFoundError:
                if show_logs:
                    Logger.debug(f"Module {module_py_name}'s config definition not found, skipped.")

        except Exception:
            if show_logs:
                Logger.exception(f"Failed to load {module_py_name}:")

    if show_logs:
        Logger.success("All modules loaded.")
    ModulesManager.refresh()
