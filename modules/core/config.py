from core.config.decorator import on_module_config


@on_module_config("bind")
class BindConfig:
    enable_bind_auto: bool = False
