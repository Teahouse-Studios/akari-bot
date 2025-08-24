from core.config.decorator import on_config


@on_config("config")
class Config:
    debug: bool = False
    base_superuser: list = ["QQ|2596322644"]
    rickroll_msg: str = ""
    enable_rickroll: bool = True
    report_targets: list = []
    tos_warning_counts: int = 5
    issue_url: str = "https://github.com/Teahouse-Studios/bot/issues/new/choose"
    enable_joke: bool = True
    shuffle_rate: float = 0.1
    unloaded_modules: list = []
    use_font_mirror: bool = False
    use_secrets_random: bool = False
    enable_petal: bool = False
    enable_get_petal: bool = False
    petal_gained_limit: int = 0
    petal_lost_limit: int = 0
    petal_sign_limit: int = 5
    petal_sign_rate: float = 0.5
    allow_request_private_ip: bool = False
    ignored_sender: list = ["QQ|2854196310"]
    enable_tos: bool = True
    enable_analytics: bool = False
    bug_report_url: str = "https://s.wd-ljt.com/botreportbug"
    tos_temp_ban_time: int = 300
    no_confirm: bool = False
    timezone_offset: str = "+8"
    confirm_command: list = ["是", "对", "對", "yes", "Yes", "YES", "y", "Y"]
    command_prefix: list = ["~", "～"]
    enable_dirty_check: bool = False
    enable_urlmanager: bool = False
    enable_eval: bool = False
    help_url: str = "https://bot.teahouse.team"
    donate_url: str = "http://afdian.com/a/teahouse"
    help_page_url: str = "https://bot.teahouse.team/wiki/${module}"
    allow_reload_base: bool = False
    enable_commit_url: bool = True
    locale_url: str = "https://www.crowdin.com/project/akari-bot"
    slower_schedule: bool = False


@on_config("secret")
class SecretConfig:
    check_access_key_id: str = ""
    check_access_key_secret: str = ""
    ff3_key: str = ""
    ff3_tweak: str = ""
    proxy: str = ""
    db_path: str = "sqlite://database/save.db"


@on_config("webrender")
class WebRenderConfig:
    enable_web_render: bool = False
    remote_web_render_url: str = ""
    browser_type: str = "chrome"
    browser_executable_path: str = ""
