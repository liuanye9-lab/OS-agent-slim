"""pytest fixture 配置文件 — StableAgent Cloud.

- 自动清理 SQLite 连接，消除 ResourceWarning
- 每次测试后关闭未释放的数据库连接
"""

from __future__ import annotations

import gc
import sqlite3
import warnings

import pytest


@pytest.fixture(autouse=True)
def _cleanup_db_connections():
    """自动清理所有 SQLite 连接（消除 ResourceWarning）。"""
    yield
    # 强制 GC + 关闭所有打开的 SQLite 连接
    gc.collect()
    # 遍历所有对象，关闭未释放的 sqlite3.Connection
    for obj in gc.get_objects():
        if isinstance(obj, sqlite3.Connection):
            try:
                obj.close()
            except Exception:
                pass


def pytest_configure(config):
    """pytest 配置钩子 — 过滤可接受的警告。"""
    # ResourceWarning 在测试环境中是已知的，但仍然尝试清理
    warnings.filterwarnings(
        "ignore",
        message=".*unclosed database.*",
        category=ResourceWarning,
    )
    # datetime.utcnow deprecation — 来自旧 test 代码
    warnings.filterwarnings(
        "ignore",
        message=".*utcnow.*deprecated.*",
        category=DeprecationWarning,
    )
