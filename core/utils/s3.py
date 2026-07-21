from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import boto3
import orjson
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from core.logger import Logger
from core.config import Config


class S3StorageAPI:
    """S3 兼容对象存储客户端，提供持久文件和临时文件的上传、列出、删除及预签名链接生成。"""

    PERSIST_PREFIX = "persist"
    TEMP_PREFIX = "temp"
    DEFAULT_TEMP_MAX_COUNT = 20
    HASH_LENGTH = 12  # first N hex chars of SHA256 embedded in filename

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        public_endpoint: str | None = None,
        internal_endpoint: str | None = None,
        temp_max_count: int = DEFAULT_TEMP_MAX_COUNT,
    ):
        self._endpoint = endpoint_url.rstrip("/")
        self.bucket = bucket
        self._public_endpoint = (public_endpoint or endpoint_url).rstrip("/")
        self._internal_endpoint = (internal_endpoint or endpoint_url).rstrip("/")
        self.temp_max_count = temp_max_count
        self._manifest_locks: dict[str, asyncio.Lock] = {}

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self._ensure_folders()
        Logger.info(f"[S3] Initialized storage client for bucket: {bucket}")

    def _ensure_folders(self):
        for prefix in (self.PERSIST_PREFIX, self.TEMP_PREFIX):
            key = f"{prefix}/"
            try:
                self._client.put_object(Bucket=self.bucket, Key=key, Body=b"")
            except ClientError as e:
                Logger.warning(f"[S3] Failed to ensure folder {key}: {e}")

    async def _run_sync(self, func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    async def upload_persist(self, file_path: str | Path, object_key: str | None = None, expires: int = 3600) -> dict:
        """上传文件到 persist 文件夹。自动计算文件 hash 并嵌入文件名，若已有同 hash 文件则跳过上传直接返回链接。

        :param file_path: 本地文件路径。
        :param object_key: 远端对象名（不含前缀），默认使用文件名。
        :param expires: 预签名链接有效期（秒）。
        :return: 包含 key、internal_url、public_url 的字典。
        """
        file_hash = self._compute_hash(file_path)
        key = self._build_key(self.PERSIST_PREFIX, file_path, object_key, file_hash)
        if await self._key_exists(key):
            Logger.info(f"[S3] Deduplicated persist (hash {file_hash}): {key}")
            return await self._build_result(key, expires)

        await self._run_sync(self._client.upload_file, str(file_path), self.bucket, key)
        await self._update_manifest(
            self.PERSIST_PREFIX,
            lambda files: files.append(
                {
                    "key": key,
                    "size": Path(file_path).stat().st_size,
                    "last_modified": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )
        Logger.info(f"[S3] Uploaded persist: {key}")
        return await self._build_result(key, expires)

    async def upload_temp(self, file_path: str | Path, object_key: str | None = None, expires: int = 3600) -> dict:
        """上传文件到 temp 文件夹，上传前检查并清理超出配额的文件。自动计算文件 hash 并嵌入文件名，若已有同 hash 文件则跳过上传直接返回链接。

        :param file_path: 本地文件路径。
        :param object_key: 远端对象名（不含前缀），默认使用文件名。
        :param expires: 预签名链接有效期（秒）。
        :return: 包含 key、internal_url、public_url 的字典。
        """
        file_hash = self._compute_hash(file_path)
        key = self._build_key(self.TEMP_PREFIX, file_path, object_key, file_hash)
        if await self._key_exists(key):
            Logger.info(f"[S3] Deduplicated temp (hash {file_hash}): {key}")
            return await self._build_result(key, expires)

        await self._run_sync(self._client.upload_file, str(file_path), self.bucket, key)

        async def _bg():
            await self._ensure_temp_quota()

            async def _append(files):
                files.append(
                    {
                        "key": key,
                        "size": Path(file_path).stat().st_size,
                        "last_modified": datetime.now(timezone.utc).isoformat(),
                    }
                )

            await self._update_manifest(self.TEMP_PREFIX, _append)

        asyncio.create_task(_bg())
        Logger.info(f"[S3] Uploaded temp: {key}")
        return await self._build_result(key, expires)

    async def list_files(self, prefix: str = "") -> list[dict]:
        """列出指定文件夹下的所有文件（从 manifest 读取，不调用 list_objects API）。

        :param prefix: 文件夹前缀，如 "persist" 或 "temp"。
        :return: 文件信息列表，每项含 key、size、last_modified。
        """
        p = prefix.rstrip("/") if prefix else self.TEMP_PREFIX
        return await self._read_manifest(p)

    # --- manifest helpers ---

    def _manifest_key(self, prefix: str) -> str:
        return f"{prefix}/.manifest.json"

    def _read_manifest_sync(self, prefix: str) -> list[dict]:
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=self._manifest_key(prefix))
            body = resp["Body"].read()
            return orjson.loads(body)
        except ClientError:
            return []

    async def _read_manifest(self, prefix: str) -> list[dict]:
        return await self._run_sync(self._read_manifest_sync, prefix)

    def _write_manifest_sync(self, prefix: str, files: list[dict]):
        body = orjson.dumps(files)
        self._client.put_object(Bucket=self.bucket, Key=self._manifest_key(prefix), Body=body)

    async def _write_manifest(self, prefix: str, files: list[dict]):
        await self._run_sync(self._write_manifest_sync, prefix, files)

    async def _update_manifest(self, prefix: str, updater):
        """在锁保护下读取 manifest、执行 updater(files)、写回（防止并发覆盖）。

        updater 可为同步或异步函数，若为异步则 await 其执行结果。
        """
        import inspect

        lock = self._manifest_locks.setdefault(prefix, asyncio.Lock())
        async with lock:
            files = await self._read_manifest(prefix)
            result = updater(files)
            if inspect.isawaitable(result):
                await result
            await self._write_manifest(prefix, files)

    async def get_presigned_url(self, object_key: str, expires: int = 3600, internal: bool = True) -> str:
        """为指定文件生成预签名链接。

        :param object_key: 对象在桶中的完整 key。
        :param expires: 链接有效期（秒）。
        :param internal: True 返回内网链接，False 返回公网链接。
        """
        url = await self._run_sync(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=expires,
        )
        target = self._internal_endpoint if internal else self._public_endpoint
        return self._replace_endpoint(url, target)

    async def delete_persist(self, filename: str) -> bool:
        """删除 persist 文件夹下的指定文件。

        :param filename: 文件名（不含 persist/ 前缀）。
        """
        key = f"{self.PERSIST_PREFIX}/{filename.lstrip('/')}"
        success = await self.delete_file(key)
        if success:
            await self._update_manifest(
                self.PERSIST_PREFIX,
                lambda files: [f for f in files if f["key"] != key],
            )
        return success

    async def delete_temp(self, filename: str) -> bool:
        """删除 temp 文件夹下的指定文件。

        :param filename: 文件名（不含 temp/ 前缀）。
        """
        key = f"{self.TEMP_PREFIX}/{filename.lstrip('/')}"
        success = await self.delete_file(key)
        if success:
            await self._update_manifest(
                self.TEMP_PREFIX,
                lambda files: [f for f in files if f["key"] != key],
            )
        return success

    async def delete_file(self, object_key: str) -> bool:
        """删除桶中的指定对象。

        :param object_key: 对象在桶中的完整 key。
        :return: 成功返回 True，失败返回 False。
        """
        try:
            await self._run_sync(self._client.delete_object, Bucket=self.bucket, Key=object_key)
            Logger.info(f"[S3] Deleted: {object_key}")
            return True
        except ClientError as e:
            Logger.error(f"[S3] Failed to delete {object_key}: {e}")
            return False

    async def generate_temp_presigned_url(self, filename: str, expires: int = 3600) -> str:
        """为 temp 文件夹下的指定文件生成公网预签名链接。

        :param filename: 文件名（不含 temp/ 前缀）。
        :param expires: 链接有效期（秒）。
        """
        return await self.get_presigned_url(f"{self.TEMP_PREFIX}/{filename}", expires, internal=False)

    # --- internal helpers ---

    async def _key_exists(self, key: str) -> bool:
        """检查指定 key 是否已存在于桶中（使用 head_object）。"""
        try:
            await self._run_sync(self._client.head_object, Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    @staticmethod
    def _compute_hash(file_path: str | Path) -> str:
        """计算文件的 SHA256 哈希，返回前 HASH_LENGTH 位 hex 字符串。

        :param file_path: 本地文件路径。
        """
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha.update(chunk)
        return sha.hexdigest()[: S3StorageAPI.HASH_LENGTH]

    async def _ensure_temp_quota(self):
        """确保 temp 文件夹文件数不超过上限，超出则删除最旧的文件。"""

        async def _cleanup(files):
            while len(files) >= self.temp_max_count:
                oldest = files.pop(0)
                await self.delete_file(oldest["key"])

        await self._update_manifest(self.TEMP_PREFIX, _cleanup)

    async def _build_result(self, key: str, expires: int) -> dict:
        internal_url, public_url = await asyncio.gather(
            self.get_presigned_url(key, expires, internal=True),
            self.get_presigned_url(key, expires, internal=False),
        )
        return {
            "key": key,
            "internal_url": internal_url,
            "public_url": public_url,
        }

    @staticmethod
    def _build_key(prefix: str, file_path: str | Path, object_key: str | None, file_hash: str) -> str:
        """构建 S3 对象 key，将 hash 嵌入文件名（在扩展名之前）。

        例: ("persist", "/tmp/data.txt", None, "a1b2c3") → "persist/data_a1b2c3.txt"
        """
        name = (object_key or Path(file_path).name).lstrip("/")
        stem, sep, ext = name.rpartition(".")
        if sep and stem:
            name = f"{stem}_{file_hash}.{ext}"
        else:
            name = f"{name}_{file_hash}"
        return f"{prefix}/{name}"

    def _replace_endpoint(self, url: str, target_endpoint: str) -> str:
        if self._endpoint == target_endpoint:
            return url
        parsed = urlparse(url)
        target_netloc = urlparse(target_endpoint).netloc
        return urlunparse(parsed._replace(netloc=target_netloc))


s3_access_key = Config("s3_access_key", cfg_type=str, table_name="s3", secret=True)
s3_secret_key = Config("s3_secret_key", cfg_type=str, table_name="s3", secret=True)
endpoint_url = Config("s3_endpoint_url", cfg_type=str, table_name="s3")
bucket = Config("s3_bucket", cfg_type=str, table_name="s3")
region = Config("s3_region", cfg_type=str, table_name="s3")


if s3_access_key and s3_secret_key and endpoint_url and bucket and region:
    S3Storage = S3StorageAPI(
        endpoint_url=endpoint_url,
        access_key=s3_access_key,
        secret_key=s3_secret_key,
        bucket=bucket,
        region=region,
        public_endpoint=Config("s3_public_endpoint", cfg_type=str, table_name="s3", default=None),
        internal_endpoint=Config("s3_internal_endpoint", cfg_type=str, table_name="s3", default=None),
        temp_max_count=Config("s3_temp_max_count", cfg_type=int, table_name="s3", default=20),
    )
else:
    Logger.warning("[S3] S3 configuration is incomplete. S3Storage will not be initialized.")
    S3Storage = None

__all__ = ["S3Storage"]
