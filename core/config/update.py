import shutil
from time import sleep

from loguru import logger
from tomlkit import parse as toml_parser, dumps as toml_dumps, document as toml_document, comment as toml_comment, nl
from tomlkit.exceptions import KeyAlreadyPresent

from core.constants import config_filename
from core.constants.exceptions import ConfigFileNotFound
from core.constants.path import config_path
from core.constants.version import config_version
from core.i18n import Locale
from core.utils.tools import is_int, is_float

cfg_file_path = config_path / config_filename
old_cfg_file_path = config_path / "config.cfg"


def convert_cfg_to_toml():
    import configparser
    config_old = configparser.ConfigParser()
    config_old.read(old_cfg_file_path)
    config_dict = {}
    for section in config_old.sections():
        config_dict[section] = {}
        config_dict[section].update(dict(config_old[section]))

    for x in config_dict:
        for y in config_dict[x]:
            if config_dict[x][y] == "True":
                config_dict[x][y] = True
            elif config_dict[x][y] == "False":
                config_dict[x][y] = False
            elif is_int(config_dict[x][y]):
                config_dict[x][y] = int(config_dict[x][y])
            elif is_float(config_dict[x][y]):
                config_dict[x][y] = float(config_dict[x][y])

    with open(cfg_file_path, "w") as f:
        f.write(toml_dumps(config_dict))
    old_cfg_file_path.unlink()


# If the config file does not exist, try to convert the old config file to the new format, or raise an error.


if not cfg_file_path.exists():
    if old_cfg_file_path.exists():
        convert_cfg_to_toml()
    else:
        raise ConfigFileNotFound(cfg_file_path) from None


class ConfigReorganizer:
    def __init__(self, old_config, configs, locale, table_prefix=""):
        self.config = old_config
        self.configs = configs
        self.locale = locale
        self.prefix = table_prefix
        self.table = ""

    def set_table(self, table_name):
        self.table = table_name

    def _init_file(self, cfg_name):
        if cfg_name not in self.configs:
            self.configs[cfg_name] = toml_document()
            self.configs[cfg_name].add(
                toml_comment(
                    self.locale.t(
                        "config.header.line.1",
                        fallback_failed_prompt=False)))
            self.configs[cfg_name].add(
                toml_comment(
                    self.locale.t(
                        "config.header.line.2",
                        fallback_failed_prompt=False)))
            self.configs[cfg_name].add(
                toml_comment(
                    self.locale.t(
                        "config.header.line.3",
                        fallback_failed_prompt=False)))

    def reorganize_key(self, key, secret=False):
        cfg_name = self.prefix + self.table
        c_target = "secret" if key in self.config.get("secret", {}) else "config"
        table = cfg_name + "_secret" if secret else cfg_name

        if key not in self.config.get(c_target, {}):
            return  # key 不存在则跳过

        self._init_file(cfg_name)

        if table not in self.configs[cfg_name]:
            self.configs[cfg_name].add(nl())
            self.configs[cfg_name].add(table, toml_document())
            if self.prefix:
                if table.endswith("_secret"):
                    qk = f"config.table.secret_{self.prefix.rstrip("_")}"
                else:
                    qk = f"config.table.config_{self.prefix.rstrip("_")}"
                self.configs[cfg_name][table].add(toml_comment(self.locale.t(qk, fallback_failed_prompt=False)))

        try:
            self.configs[cfg_name][table].add(key, self.config[c_target][key])
        except KeyAlreadyPresent:
            self.configs[cfg_name][table][key] = self.config[c_target][key]

        qc = f"config.comments.{key}"
        localed_comment = self.locale.t(qc, fallback_failed_prompt=False)
        if localed_comment != qc:
            self.configs[cfg_name][table].value.item(key).comment(localed_comment)

        self.config[c_target].pop(key)

    def add_enable_flag(self):
        cfg_name = self.prefix + self.table
        self._init_file(cfg_name)
        if cfg_name not in self.configs[cfg_name]:
            self.configs[cfg_name].add(nl())
            self.configs[cfg_name].add(cfg_name, toml_document())
            self.configs[cfg_name][cfg_name].add(
                toml_comment(
                    self.locale.t("config.table.config_bot", fallback_failed_prompt=False)
                )
            )
        try:
            self.configs[cfg_name][cfg_name].add("enable", True)
        except KeyAlreadyPresent:
            self.configs[cfg_name][cfg_name]["enable"] = True

        qc = "config.comments.enable"
        localed_comment = self.locale.t(qc, fallback_failed_prompt=False)
        if localed_comment != qc:
            self.configs[cfg_name][cfg_name].value.item("enable").comment(localed_comment)

        if "disabled_bots" in self.config.get("config", {}):
            if self.table in self.config["config"]["disabled_bots"]:
                self.configs[cfg_name][cfg_name]["enable"] = False


# Load the config file
with open(cfg_file_path, "r", encoding="utf-8") as cfg_file:
    config = toml_parser(cfg_file.read())

# If config version not exists, regenerate the config file (assumed as
# version 0 to convert old to new format since this is the first time to
# generate the config file for everyone)
if "config_version" not in config:
    old_config = config
    logger.info("Config version not found, regenerating the config file...")
    shutil.copy(cfg_file_path, str(cfg_file_path) + ".bak")
    configs = {"config": toml_document()}
    if "cfg" in old_config:
        get_old_locale = old_config["cfg"].get("locale", "zh_cn")
    else:
        get_old_locale = "zh_cn"
    old_locale = Locale(get_old_locale)
    configs["config"].add(toml_comment(old_locale.t("config.header.line.1", fallback_failed_prompt=False)))
    configs["config"].add(toml_comment(old_locale.t("config.header.line.2", fallback_failed_prompt=False)))
    configs["config"].add(toml_comment(old_locale.t("config.header.line.3", fallback_failed_prompt=False)))
    configs["config"].add(nl())

    configs["config"].add("default_locale", get_old_locale)
    configs["config"].item("default_locale").comment(old_locale.t(
        "config.comments.default_locale",
        fallback_failed_prompt=False))

    configs["config"].add("config_version", 0)
    configs["config"].item("config_version").comment(old_locale.t(
        "config.comments.default_locale",
        fallback_failed_prompt=False))
    configs["config"].add(nl())

    # reorganize some keys
    reorganizer = ConfigReorganizer(old_config, configs, old_locale, table_prefix="bot_")

    reorganizer.set_table("aiocqhttp")
    reorganizer.add_enable_flag()
    reorganizer.reorganize_key("qq_host")
    reorganizer.reorganize_key("qq_enable_listening_self_message")
    reorganizer.reorganize_key("qq_disable_temp_session")
    reorganizer.reorganize_key("qq_allow_approve_friend")
    reorganizer.reorganize_key("qq_allow_approve_group_invite")
    reorganizer.reorganize_key("qq_limited_emoji")
    reorganizer.reorganize_key("qq_typing_emoji")
    reorganizer.reorganize_key("qq_initiative_msg_cooldown")
    reorganizer.reorganize_key("qq_access_token", True)

    reorganizer.set_table("aiogram")
    reorganizer.add_enable_flag()
    reorganizer.reorganize_key("telegram_api_url")
    reorganizer.reorganize_key("telegram_token", True)

    reorganizer.set_table("discord")
    reorganizer.add_enable_flag()
    reorganizer.reorganize_key("discord_token", True)

    reorganizer.set_table("kook")
    reorganizer.add_enable_flag()
    reorganizer.reorganize_key("kook_token", True)

    reorganizer.set_table("matrix")
    reorganizer.add_enable_flag()
    reorganizer.reorganize_key("matrix_homeserver")
    reorganizer.reorganize_key("matrix_user")
    reorganizer.reorganize_key("matrix_device_name")
    reorganizer.reorganize_key("matrix_device_id", True)
    reorganizer.reorganize_key("matrix_token", True)
    reorganizer.reorganize_key("matrix_megolm_backup_passphrase", True)

    reorganizer.set_table("qqbot")
    reorganizer.add_enable_flag()
    reorganizer.reorganize_key("qq_bot_appid")
    reorganizer.reorganize_key("qq_private_bot")
    reorganizer.reorganize_key("qq_bot_enable_send_url")
    reorganizer.reorganize_key("qq_typing_emoji")
    reorganizer.reorganize_key("qq_bot_secret", True)

    reorganizer.set_table("web")
    reorganizer.add_enable_flag()
    reorganizer.reorganize_key("enable_https")
    reorganizer.reorganize_key("web_host")
    reorganizer.reorganize_key("web_port")
    reorganizer.reorganize_key("login_max_attempt")
    reorganizer.reorganize_key("heartbeat_attempt")
    reorganizer.reorganize_key("heartbeat_interval")
    reorganizer.reorganize_key("heartbeat_timeout")
    reorganizer.reorganize_key("jwt_secret", True)

    configs["config"].add("config", toml_document())
    configs["config"]["config"].add(toml_comment(old_locale.t("config.table.config")))
    if "cfg" in config:
        for k, v in config["cfg"].items():
            configs["config"]["config"][k] = v
            qc = "config.comments." + k
            localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
            if localed_comment != qc:
                configs["config"]["config"].value.item(k).comment(localed_comment)
    configs["config"].add(nl())

    configs["config"].add("secret", toml_document())
    configs["config"]["secret"].add(toml_comment(old_locale.t("config.table.config")))
    if "secret" in config:
        for k, v in config["secret"].items():
            configs["config"]["secret"][k] = v
            qc = "config.comments." + k
            localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
            if localed_comment != qc:
                configs["config"]["secret"].value.item(k).comment(localed_comment)

    if "locale" in configs["config"]["config"]:
        configs["config"]["config"].pop("locale")
    if "disabled_bots" in configs["config"]["config"]:
        configs["config"]["config"].pop("disabled_bots")

    for c in configs:
        filename = c
        if not c.endswith(".toml"):
            filename += ".toml"
        with open(config_path / filename, "w", encoding="utf-8") as f:
            f.write(toml_dumps(configs[c]))
    logger.success("Config file regenerated successfully.")
    sleep(3)
    with open(cfg_file_path, "r", encoding="utf-8") as cfg_file:
        config = toml_parser(cfg_file.read())  # Reload the config file after regeneration
if config["config_version"] < config_version:
    logger.info(f"Updating Config file from {config["config_version"]} to {config_version}...")
    if config["config_version"] < 1:
        with open(cfg_file_path, "r", encoding="utf-8") as f:
            config = toml_parser(f.read())
        locale = Locale(config.get("locale", "zh_cn"))
        configs = {}

        reorganizer = ConfigReorganizer(config, configs, locale, table_prefix="module_")
        reorganizer.set_table("ai")
        reorganizer.reorganize_key("llm_max_tokens")
        reorganizer.reorganize_key("llm_temperature")
        reorganizer.reorganize_key("llm_top_p")
        reorganizer.reorganize_key("llm_frequency_penalty")
        reorganizer.reorganize_key("llm_presence_penalty")
        reorganizer.reorganize_key("ai_default_llm")

        reorganizer.set_table("coin")
        reorganizer.reorganize_key("coin_limit")
        reorganizer.reorganize_key("coin_faceup_weight")
        reorganizer.reorganize_key("coin_facedown_weight")
        reorganizer.reorganize_key("coin_stand_weight")

        reorganizer.set_table("dice")
        reorganizer.reorganize_key("dice_limit")
        reorganizer.reorganize_key("dice_output_count")
        reorganizer.reorganize_key("dice_output_len")
        reorganizer.reorganize_key("dice_output_digit")
        reorganizer.reorganize_key("dice_roll_limit")
        reorganizer.reorganize_key("dice_detail_count")
        reorganizer.reorganize_key("dice_count_limit")

        reorganizer.set_table("exchange_rate")
        reorganizer.reorganize_key("exchange_rate_api_key", True)

        reorganizer.set_table("github")
        reorganizer.reorganize_key("github_pat", True)

        reorganizer.set_table("maimai")
        reorganizer.reorganize_key("diving_fish_developer_token", True)

        reorganizer.set_table("mod_dl")
        reorganizer.reorganize_key("curseforge_api_key", True)

        reorganizer.set_table("ncmusic")
        reorganizer.reorganize_key("ncmusic_enable_card")
        reorganizer.reorganize_key("ncmusic_api", True)

        reorganizer.set_table("wiki")
        reorganizer.reorganize_key("wiki_whitelist_url")

        reorganizer.set_table("wolframalpha")
        reorganizer.reorganize_key("wolfram_alpha_appid", True)

        reorganizer.set_table("wordle")
        reorganizer.reorganize_key("wordle_disable_image")

        config["config_version"] = 1
        for c in configs:
            filename = c
            if not c.endswith(".toml"):
                filename += ".toml"
            with open(config_path / filename, "w", encoding="utf-8") as f:
                f.write(toml_dumps(configs[c]))
        with open(cfg_file_path, "w", encoding="utf-8") as f:
            f.write(toml_dumps(config))
        with open(cfg_file_path, "r", encoding="utf-8") as cfg_file:
            config = toml_parser(cfg_file.read())  # Reload the config file after regeneration

    if config["config_version"] < 2:
        with open(cfg_file_path, "r", encoding="utf-8") as f:
            config = toml_parser(f.read())
        locale = Locale(config.get("locale", "zh_cn"))
        configs = {}

        reorganizer = ConfigReorganizer(config, configs, locale, table_prefix="webrender")
        reorganizer.reorganize_key("enable_web_render")
        reorganizer.reorganize_key("browser_type")
        reorganizer.reorganize_key("browser_executable_path")
        reorganizer.reorganize_key("remote_web_render_url")

        config["config_version"] = 2
        for c in configs:
            filename = c
            if not c.endswith(".toml"):
                filename += ".toml"
            with open(config_path / filename, "w", encoding="utf-8") as f:
                f.write(toml_dumps(configs[c]))
        with open(cfg_file_path, "w", encoding="utf-8") as f:
            f.write(toml_dumps(config))
        with open(cfg_file_path, "r", encoding="utf-8") as cfg_file:
            config = toml_parser(cfg_file.read())  # Reload the config file after regeneration

    logger.success("Config file updated successfully.")
    sleep(3)
