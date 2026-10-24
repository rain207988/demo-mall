"""测试辅助接口（带 X-Test-Key 钥匙才可用）。

为什么被测系统要自带"测试后门"：
- 测试要可重复，前提是"每次跑之前世界是确定的"——/api/test/reset 就是
  把数据库一键还原成种子状态，比每个用例自己清理干净得多；
- /api/test/revoke-token 用来制造真实的 401，练习"token 失效自动重登"。
真实项目里这类能力由测试环境管理平台提供。
"""

from flask import Blueprint, request

from config import TEST_KEY
from app.errors import ok, fail
from app import auth

test_bp = Blueprint("test_api", __name__, url_prefix="/api/test")


def _check_test_key():
    if request.headers.get("X-Test-Key") != TEST_KEY:
        return fail(4010, message="测试钥匙缺失", http_status=403)


@test_bp.post("/reset")
def reset_data():
    guard = _check_test_key()
    if guard:
        return guard
    # 延迟导入避免循环依赖：seed.py 会 import app
    import seed
    seed.reset_database()
    return ok({"reset": True})


@test_bp.post("/revoke-token")
def revoke_token():
    guard = _check_test_key()
    if guard:
        return guard
    body = request.get_json(silent=True) or {}
    token = body.get("token") or ""
    if not token:
        return fail(1004, "缺少 token")
    if not auth.revoke_token(token):
        return fail(1004, "token 无效，无法吊销")
    return ok({"revoked": True})
