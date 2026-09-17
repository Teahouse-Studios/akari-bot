"""Tortoise ORM 兼容补丁。

Tortoise 1.1 的 SQLite 事务上下文在 ``__aenter__`` 里先取连接锁，再执行
``BEGIN``；若任务在这两步之间被取消（例如关闭超时取消了一个
``registry.unregister``），``__aexit__`` 永远不会执行，连接锁便再也无人释放。
SQLite 后端全进程共用这一把锁，此后所有数据库操作都会静默挂起。补丁让
``__aenter__`` 在失败或取消时回滚并释放连接锁，与 ``__aexit__`` 的清理语义一致。
"""

from __future__ import annotations

from tortoise.backends.sqlite.client import SqliteTransactionContext
from tortoise.connection import get_connections

_installed = False


async def _cancellation_safe_aenter(self):
    await self._trxlock.acquire()
    token = None
    try:
        await self.ensure_connection()
        token = get_connections().set(self.connection_name, self.connection)
        self.token = token
        await self.connection.begin()
    except BaseException:
        try:
            if self.connection._connection is not None:
                await self.connection.rollback()
        except BaseException:
            pass
        if token is not None:
            get_connections().reset(token)
        self._trxlock.release()
        raise
    return self.connection


def install_tortoise_sqlite_transaction_compat() -> None:
    """安装 SQLite 事务上下文的取消安全补丁，可重复调用。"""
    global _installed
    if _installed:
        return
    SqliteTransactionContext.__aenter__ = _cancellation_safe_aenter
    _installed = True


__all__ = ["install_tortoise_sqlite_transaction_compat"]
