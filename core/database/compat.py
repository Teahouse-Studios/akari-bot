"""Tortoise ORM 兼容补丁。

Tortoise 1.1 在几处「先占用资源、再开启事务」的路径上只按正常流程清理，
任务被取消（``CancelledError`` 不属于 ``Exception``）时资源会泄漏：

SQLite 后端：
1. ``SqliteTransactionContext.__aenter__`` 先取连接锁再执行 ``BEGIN``；若在两步
   之间被取消（例如关闭超时取消了一个 ``registry.unregister``），``__aexit__``
   永远不会执行，连接锁再也无人释放。SQLite 后端全进程共用这一把锁，此后所有
   数据库操作都会静默挂起。
2. ``SqliteTransactionContext.__aexit__`` 在 ``commit``/``rollback`` 被取消或失败
   时直接进入 ``finally`` 释放锁，事务本身可能仍处于打开状态。
3. ``SqliteClient.execute_many`` 自行 ``BEGIN``/``commit``，却只在
   ``except Exception`` 里回滚；取消抛出的 ``CancelledError`` 会跳过回滚，把连接
   留在已打开的事务里，下一次批量写入就会报
   ``cannot start a transaction within a transaction``。

池化后端（MySQL 等，生产环境主库）：
4. ``TransactionContextPooled.__aenter__`` 先从连接池取走连接再执行 ``BEGIN``；
   若在 ``begin`` 期间被取消，连接永远不会归还连接池，也不会回滚，反复发生会
   耗尽池容量，此后所有查询都在 ``acquire`` 上阻塞。``asyncmy`` 归还仍在事务中
   的连接时会直接关闭它，因此这里要先回滚再归还。
5. ``TransactionContextPooled.__aexit__`` 的 ``commit``/``rollback`` 失败或取消时
   没有兜底回滚，且归还连接若抛错会跳过连接上下文的复位。
6. ``MySQLClient.execute_many`` 与 SQLite 同款：只捕获 ``Exception``，取消时不回滚。

补丁让这些路径在失败或取消时回滚并释放资源，与正常退出路径的清理语义一致。
"""

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
