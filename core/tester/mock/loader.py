import importlib
import pkgutil

from core.i18n import load_locale_file
from core.loader import ModulesManager
from core.logger import Logger


def apply_monkey_patch(module, monkey_patches: dict[str, object] | None):
    if not monkey_patches:
        return

    for name, mock_obj in monkey_patches.items():
        if hasattr(module, name):
            setattr(module, name, mock_obj)


async def load_modules(show_logs=True, monkey_patches: dict[str, object] | None = None):
    import modules

    err_prompt = []
    locale_loaded_err = load_locale_file()
    if locale_loaded_err:
        err_prompt.append("I18N loaded failed:")
        err_prompt.append("\n".join(locale_loaded_err))

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
                    Logger.debug(
                        f"Successfully loaded {module_py_name}'s config definition!"
                    )
            except ModuleNotFoundError:
                if show_logs:
                    Logger.debug(
                        f"Module {module_py_name}'s config definition not found, skipped."
                    )

        except Exception:
            if show_logs:
                Logger.exception(f"Failed to load {module_py_name}:")

    if show_logs:
        Logger.success("All modules loaded.")
    ModulesManager.refresh()
