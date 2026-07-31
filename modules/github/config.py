from core.config.decorator import on_module_config


@on_module_config("github", secret=True)
class GithubConfig:
    github_pat: str = ""
