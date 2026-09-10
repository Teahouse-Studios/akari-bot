"""S3 兼容对象存储配置模板。"""

from core.config.decorator import on_config


@on_config("s3")
class S3Config:
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_public_endpoint: str = ""
    s3_internal_endpoint: str = ""
    s3_temp_max_count: int = 20
    s3_connect_timeout: float = 30
    s3_read_timeout: float = 30
    s3_operation_timeout: float = 60
    s3_max_attempts: int = 2
    s3_max_workers: int = 4


@on_config("s3", secret=True)
class S3SecretConfig:
    s3_access_key: str = ""
    s3_secret_key: str = ""
