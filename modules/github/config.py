from . import github


@github.config(secret=True)
class GithubConfig:
    github_pat: str = ""
