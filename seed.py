"""初始化 / 重置数据库到"种子状态"。

用法：
    python seed.py            # 已有库则保留，缺表才建
    python seed.py --reset    # 清空重建 + 重新灌种子数据（CI/跑测试前用这个）

种子数据设计原则：确定性——测试框架的断言（价格、总数）全依赖这些固定值，
所以任何改动都要同步通知 api-test-framework 的 data/ 目录。
"""

import argparse
import os
import sqlite3

from config import DB_PATH, BASE_DIR

SEED_USERS = [
    # (username, password, nickname) —— 密码明文仅存于本文档；库里只存摘要
    ("lemon", "123456", "柠檬"),
    ("test", "123456", "测试号"),
]

SEED_GOODS = [
    # (name, category, price, stock, description)
    ("无线蓝牙耳机", "手机数码", 199.00, 50, "半入耳式，续航24小时"),
    ("智能手表 Pro", "手机数码", 1299.00, 30, "心率监测+GPS"),
    ("快充充电器 65W", "手机数码", 89.00, 100, "支持PD/QC协议"),
    ("机械键盘 87键", "电脑外设", 329.00, 40, "红轴，白光"),
    ("无线鼠标 M3", "电脑外设", 79.00, 120, "静音微动，2.4G"),
    ("4K显示器 27寸", "电脑外设", 1499.00, 15, "IPS面板，Type-C"),
    ("保温杯 500ml", "家居生活", 49.90, 200, "316不锈钢，12小时保温"),
    ("记忆棉枕头", "家居生活", 99.00, 80, "慢回弹，可拆洗"),
    ("坚果大礼包", "食品饮料", 128.00, 60, "每日坚果8袋装"),
    ("挂耳咖啡 30包", "食品饮料", 68.00, 90, "中深烘焙"),
]


def init_schema(conn: sqlite3.Connection):
    with open(os.path.join(BASE_DIR, "app", "schema.sql"), encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def seed_data(conn: sqlite3.Connection):
    from app.auth import hash_password
    for username, password, nickname in SEED_USERS:
        conn.execute("INSERT INTO users(username, password_hash, nickname) VALUES(?,?,?)",
                     (username, hash_password(password), nickname))
    for name, category, price, stock, desc in SEED_GOODS:
        conn.execute("INSERT INTO goods(name, category, price, stock, description) VALUES(?,?,?,?,?)",
                     (name, category, price, stock, desc))
    conn.commit()


def reset_database():
    """清空所有业务表并重新灌入种子数据（供 /api/test/reset 和本脚本 --reset 使用）。"""
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        init_schema(conn)
        seed_data(conn)
        conn.close()
        return
    conn = sqlite3.connect(DB_PATH)
    init_schema(conn)
    for table in ("order_items", "orders", "cart_items", "goods", "users"):
        conn.execute(f"DELETE FROM {table}")
        # 重置自增 id，保证 reset 后 goods_id=1 还是第一件商品（测试断言依赖确定性）
        try:
            conn.execute(f"DELETE FROM sqlite_sequence WHERE name = '{table}'")
        except sqlite3.OperationalError:
            pass  # sqlite_sequence 在产生第一个自增值前不存在
    seed_data(conn)
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="demo-mall 数据库初始化工具")
    parser.add_argument("--reset", action="store_true", help="清空并重建全部数据")
    args = parser.parse_args()

    if args.reset or not os.path.exists(DB_PATH):
        reset_database()
        print(f"[seed] 数据库已重置为种子状态：{DB_PATH}")
    else:
        conn = sqlite3.connect(DB_PATH)
        init_schema(conn)
        conn.close()
        print(f"[seed] 数据库已存在，仅确保表结构存在：{DB_PATH}")


if __name__ == "__main__":
    main()
