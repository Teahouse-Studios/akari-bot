"""Tortoise ORM 兼容补丁。"""

from __future__ import annotations

from tortoise.backends.base.client import TransactionContextPooled
from tortoise.backends.sqlite.client import SqliteClient, SqliteTransactionContext
from tortoise.backends.sqlite.client import translate_exceptions as sqlite_translate_exceptions
from tortoise.connection import get_connections
from tortoise.exceptions import TransactionManagementError

try:
    from tortoise.backends.mysql.client import MySQLClient
    from tortoise.backends.mysql.client import translate_exceptions as mysql_translate_exceptions
except ImportError:  # pragma: no cover - 未安装 MySQL 驱动时跳过 MySQL 补丁
    MySQLClient = None

    def mysql_translate_exceptions(func):
        return func


_installed = False


async def _rollback_quietly(connection) -> None:
    try:
        if connection._connection is not None:
            await connection.rollback()
    except BaseException:
        pass


async def _cancellation_safe_sqlite_aenter(self):
    await self._trxlock.acquire()
    token = None
    try:
        await self.ensure_connection()
        token = get_connections().set(self.connection_name, self.connection)
        self.token = token
        await self.connection.begin()
    except BaseException:
        await _rollback_quietly(self.connection)
        if token is not None:
            get_connections().reset(token)
        self._trxlock.release()
        raise
    return self.connection


async def _cancellation_safe_sqlite_aexit(self, exc_type, exc_val, exc_tb):
    try:
        if not self.connection._finalized:
            if exc_type:
                if exc_type is not TransactionManagementError:
                    await self.connection.rollback()
            else:
                await self.connection.commit()
    except BaseException:
        await _rollback_quietly(self.connection)
        raise
    finally:
        get_connections().reset(self.token)
        self._trxlock.release()


@sqlite_translate_exceptions
async def _cancellation_safe_sqlite_execute_many(self, query: str, values: list[list]) -> None:
    async with self.acquire_connection() as connection:
        self.log.debug("%s: %s", query, values)
        try:
            await connection.execute("BEGIN")
            await connection.executemany(query, values)
            await connection.commit()
        except BaseException:
            try:
                await connection.rollback()
            except BaseException:
                pass
            raise


async def _cancellation_safe_pooled_aenter(self):
    await self.ensure_connection()
    connection = await self.client._parent._pool.acquire()
    self.client._connection = connection
    token = get_connections().set(self.connection_name, self.client)
    self.token = token
    try:
        await self.client.begin()
    except BaseException:
        try:
            await self.client.rollback()
        except BaseException:
            pass
        get_connections().reset(token)
        try:
            await self.client._parent._pool.release(connection)
        except BaseException:
            pass
        raise
    return self.client


async def _cancellation_safe_pooled_aexit(self, exc_type, exc_val, exc_tb):
    try:
        if not self.client._finalized:
            if exc_type:
                if exc_type is not TransactionManagementError:
                    await self.client.rollback()
            else:
                await self.client.commit()
    except BaseException:
        try:
            await self.client.rollback()
        except BaseException:
            pass
        raise
    finally:
        try:
            if self.client._parent._pool:
                await self.client._parent._pool.release(self.client._connection)
        except BaseException:
            pass
        get_connections().reset(self.token)


@mysql_translate_exceptions
async def _cancellation_safe_mysql_execute_many(self, query: str, values: list[list]) -> None:
    async with self.acquire_connection() as connection:
        self.log.debug("%s: %s", query, values)
        async with connection.cursor() as cursor:
            if not self.capabilities.supports_transactions:
                await cursor.executemany(query, values)
                return
            try:
                await connection.begin()
                await cursor.executemany(query, values)
                await connection.commit()
            except BaseException:
                try:
                    await connection.rollback()
                except BaseException:
                    pass
                raise


def install_tortoise_transaction_compat() -> None:
    """安装各后端事务与批量写入的取消安全补丁，可重复调用。"""
    global _installed
    if _installed:
        return
    SqliteTransactionContext.__aenter__ = _cancellation_safe_sqlite_aenter
    SqliteTransactionContext.__aexit__ = _cancellation_safe_sqlite_aexit
    SqliteClient.execute_many = _cancellation_safe_sqlite_execute_many
    TransactionContextPooled.__aenter__ = _cancellation_safe_pooled_aenter
    TransactionContextPooled.__aexit__ = _cancellation_safe_pooled_aexit
    if MySQLClient is not None:
        MySQLClient.execute_many = _cancellation_safe_mysql_execute_many
    _installed = True


__all__ = ["install_tortoise_transaction_compat"]
