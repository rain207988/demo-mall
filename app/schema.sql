-- demo-mall 数据库结构（SQLite）
-- 设计原则：只保留教学必需的表和字段；每张表都能在接口测试里被"读到或写到"。

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,           -- pbkdf2_hmac 摘要，存十六进制
    nickname      TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS goods (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT '其他',
    price       REAL    NOT NULL,             -- 演示用 REAL；真实电商用分(整数)存，避免浮点误差
    stock       INTEGER NOT NULL DEFAULT 0,
    description TEXT    NOT NULL DEFAULT '',
    on_sale     INTEGER NOT NULL DEFAULT 1     -- 1 上架 / 0 下架
);

CREATE TABLE IF NOT EXISTS cart_items (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    goods_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    added_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(user_id, goods_id)                   -- 同一商品同一用户只有一条记录，重复加购=数量累加
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no     TEXT    NOT NULL UNIQUE,
    user_id      INTEGER NOT NULL,
    total_amount REAL    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending',   -- pending 待支付 / paid 已支付 / cancelled 已取消
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    paid_at      TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL,
    goods_id   INTEGER NOT NULL,
    goods_name TEXT    NOT NULL,                -- 下单时快照商品名/价格，之后改商品不影响历史订单
    price      REAL    NOT NULL,
    quantity   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cart_user  ON cart_items(user_id);
CREATE INDEX IF NOT EXISTS idx_order_user ON orders(user_id);
