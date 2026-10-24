"""应用工厂 create_app。

为什么用"应用工厂"而不是一个 app.py 写到底：
- 测试框架/压测脚本以后要用不同的配置实例化 app（比如内存库），
  工厂模式是 Flask 官方推荐、也是企业项目标配；
- 蓝图按"业务域"拆分，接口测试框架的 api/ 层类（LoginApi/GoodsApi...）
  和这里的蓝图一一对应，两边讲得清"哪个接口在哪个文件"。
"""

import os

from flask import Flask, jsonify

from config import DB_PATH, JWT_SECRET
from app import db, auth


def create_app() -> Flask:
    app = Flask(__name__)
    # session/flash 必需；Web 登录态用它签名 cookie（与 API 的 JWT 是两套独立机制）
    app.secret_key = JWT_SECRET

    # 初始化数据库文件（首次启动自动建表）
    if not os.path.exists(DB_PATH):
        init_db_file()

    app.teardown_appcontext(db.close_db)

    # ---- 健康检查：CI 流水线里用它判断"被测系统是否就绪" ----
    @app.get("/api/health")
    def health():
        return jsonify({"code": 0, "message": "ok", "data": {"status": "up"}})

    # ---- 注册各业务蓝图 ----
    from app.api.auth_api import auth_bp
    from app.api.goods_api import goods_bp
    from app.api.cart_api import cart_bp
    from app.api.order_api import order_bp
    from app.api.test_api import test_bp
    from app.web.views import web_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(goods_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(test_bp)
    app.register_blueprint(web_bp)

    return app


def init_db_file():
    """执行 schema.sql 建表。"""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    with open(os.path.join(os.path.dirname(db.__file__), "schema.sql"), encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
