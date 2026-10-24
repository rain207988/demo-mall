"""认证接口：注册 / 登录 / 查看当前用户。"""

from flask import Blueprint, request

from app import db, auth
from app.errors import ok, fail

auth_bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    nickname = (body.get("nickname") or username).strip()

    # 参数校验：缺参 → 1004。反向用例最爱打这里
    if not username or not password:
        return fail(1004)
    if len(password) < 6:
        return fail(1004, "密码至少 6 位")

    if db.query_one("SELECT id FROM users WHERE username = ?", (username,)):
        return fail(1003)

    conn = db.get_db()
    cur = conn.execute(
        "INSERT INTO users(username, password_hash, nickname) VALUES(?,?,?)",
        (username, auth.hash_password(password), nickname),
    )
    conn.commit()
    return ok({"user_id": cur.lastrowid, "username": username})


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    username = body.get("username") or ""
    password = body.get("password") or ""

    if not username or not password:
        return fail(1004)

    user = db.query_one("SELECT * FROM users WHERE username = ?", (username,))
    if not user:
        return fail(1001)          # 注意：用户不存在和密码错误分开返回（演示用；真实系统常合并防撞库）
    if not auth.verify_password(password, user["password_hash"]):
        return fail(1002)

    token_info = auth.issue_token(user["id"], user["username"])
    return ok({
        "token": token_info["token"],
        "expires_in": token_info["expires_in"],
        "user": {"user_id": user["id"], "username": user["username"], "nickname": user["nickname"]},
    })


@auth_bp.get("/me")
@auth.login_required
def me(payload):
    """需要 token 的探针接口：UI 未登录跳转、token 关联测试都用它。"""
    user = db.query_one("SELECT id, username, nickname FROM users WHERE id = ?", (payload["user_id"],))
    if not user:
        return fail(1001)
    return ok({"user_id": user["id"], "username": user["username"], "nickname": user["nickname"]})
