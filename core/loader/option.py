from core.elements import Option
from . import ModulesManager


def add_option(
        bind_prefix,
        alias=None,
        help_doc=None,
        need_admin=False,
        need_superuser=False,
):
    ModulesManager.add_module(Option(bind_prefix=bind_prefix,
                                     help_doc=help_doc,
                                     alias=alias,
                                     need_admin=need_admin,
                                     need_superuser=need_superuser))