from . import test


@test.config()
class TestModuleConfig:
    """
    Use item function or a simple value to define the configuration for the module.
    for example:
        config_1: str = "default_value"
        config_2: int = item(42, table_name="test_table")
    """
