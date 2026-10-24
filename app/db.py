"""SQLite 连接与通用小工具。

为什么用 sqlite3 而不是 MySQL：
- 目标是"任何人 clone 后一条命令把被测系统跑起来"，零安装零配置；
- 表结构与 SQL 写法和 MySQL 几乎一致，换 MySQL 只动 db.py 一个文件（见 README）。
"""

import sqlite3

from flask import g

from config import DB_PATH


def get_db() -> sqlite3.Connection:
    """Flask 的 g 对象：一个请求周期内复用同一个连接，请求结束自动关闭。

    row_factory 设为 Row，让我们能用 row["name"] 按列名取值，
    再也不用脆弱的 row[2] 下标。
    """
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_one(sql: str, args: tuple = ()):
    """查一行，没有返回 None。"""
    return get_db().execute(sql, args).fetchone()


def query_all(sql: str, args: tuple = ()):
    """查多行，恒返回 list（空结果也是 []，调用方不用判 None）。"""
    return get_db().execute(sql, args).fetchall()
