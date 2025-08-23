from . import github

@github.config(is_secret=True)
class GithubConfig:
    """
    GitHub module configuration items.
    """
    github_pat: str = ""
