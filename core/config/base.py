from core.config.decorator import on_config
from core.constants.default import (
    base_superuser_default,
    bug_report_url_default,
    command_prefix_default,
    confirm_command_default,
    db_path_default,
    donate_url_default,
    help_url_default,
    help_page_url_default,
    ignored_sender_default,
    issue_url_default,
    locale_url_default)


@on_config("config")
class Config:
    # 调试与运行
    debug: bool = False
    timezone_offset: str = "+8"
    allow_reload_base: bool = False
    allow_request_private_ip: bool = False
    slower_schedule: bool = False
    use_font_mirror: bool = False
    use_secrets_random: bool = False

    # 身份与权限
    base_superuser: list = base_superuser_default
    ignored_sender: list = ignored_sender_default
    report_targets: list = []

    # 命令交互
    command_prefix: list = command_prefix_default
    confirm_command: list = confirm_command_default
    enable_module_invalid_prompt: bool = False
    mention_required: bool = False
    no_confirm: bool = False
    quick_confirm: bool = True

    # 通用功能
    enable_analytics: bool = True
    enable_commit_url: bool = True
    enable_dirty_check: bool = False
    check_use_textscan_v1: bool = False
    enable_urlmanager: bool = False
    auto_purge_crontab: str = "0 0 * * *"

    # 拼写检查
    typo_check_module_score: float = 0.6
    typo_check_command_score: float = 0.3
    typo_check_args_score: float = 0.5
    typo_check_options_score: float = 0.3

    # TOS
    enable_tos: bool = True
    tos_warning_counts: int = 5
    tos_temp_ban_time: int = 300

    # 花瓣
    enable_petal: bool = False
    enable_get_petal: bool = False
    petal_gained_limit: int = 0
    petal_lost_limit: int = 0
    petal_sign_limit: int = 5
    petal_sign_rate: float = 0.5

    # 玩笑
    enable_joke: bool = True
    shuffle_rate: float = 0.1
    enable_rickroll: bool = True
    rickroll_msg: str = "https://b23.tv/vXaKjqJ"

    # 外部链接
    bug_report_url: str = bug_report_url_default
    donate_url: str = donate_url_default
    help_url: str = help_url_default
    help_page_url: str = help_page_url_default
    issue_url: str = issue_url_default
    locale_url: str = locale_url_default


@on_config("secret")
class SecretConfig:
    db_path: str = db_path_default
    proxy: str = ""
    check_access_key_id: str = ""
    check_access_key_secret: str = ""
    ff3_key: str = ""
    ff3_tweak: str = ""


@on_config("webrender")
class WebRenderConfig:
    enable_web_render: bool = False
    browser_type: str = "chrome"
    browser_executable_path: str = ""
    remote_only: bool = False
    remote_web_render_url: str = ""
