"""JWT 签发与校验，以及内存版"token 吊销名单"。

教学要点：
- JWT 三段式 header.payload.signature，payload 里的 exp(过期时间)/jti(唯一id)
  就是接口测试里最常打交道的两个字段；
- 真实系统的"token 失效"通常是 Redis 黑名单或服务端 session，
  这里用进程内 set 模拟——重启即清空，够练习"401→重登→重放"了。
"""

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta

import jwt
from flask import current_app, request

from config import JWT_SECRET, TOKEN_EXPIRE_SECONDS

# 已被 /api/test/revoke-token 吊销的 jti 集合（进程内存，重启清空）
_revoked_jti: set[str] = set()


def hash_password(password: str, salt: str = "demo-mall-salt") -> str:
    """pbkdf2_hmac 摘要。真实项目用 bcrypt/passlib，原理相同：存摘要不存明文。"""
    return hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def issue_token(user_id: int, username: str) -> dict:
    """签发 token，返回 {token, expires_in}——和真实系统登录接口的返回结构对齐。"""
    now = datetime.utcnow()
    payload = {
        "user_id": user_id,
        "username": username,
        "jti": uuid.uuid4().hex,                 # token 唯一 id，吊销靠它
        "exp": now + timedelta(seconds=TOKEN_EXPIRE_SECONDS),
        "iat": now,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"token": token, "expires_in": TOKEN_EXPIRE_SECONDS}


def decode_token(token: str) -> dict:
    """校验 token：签名错/过期抛 PyJWT 异常，已吊销返回 None。

    统一返回 None 表示"不合法"，调用方一律回 4010，不区分细节——
    对外暴露"token 过期还是被吊销"属于安全信息泄露。
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("jti") in _revoked_jti:
        return None
    return payload


def revoke_token(token: str) -> bool:
    payload = decode_token(token)
    if not payload:
        return False
    _revoked_jti.add(payload["jti"])
    return True


def get_token_payload():
    """从请求头 Authorization: Bearer <token> 里取出 payload。

    这是全系统鉴权的"标准入口"——和真实后端一个拦截器/中间件干的事一样。
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return decode_token(auth[7:])


def login_required(func):
    """API 蓝图专用装饰器：拿不到合法 payload 就直接 4010。"""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        payload = get_token_payload()
        if not payload:
            from app.errors import auth_required_fail
            return auth_required_fail()
        return func(*args, payload=payload, **kwargs)

    return wrapper


def current_epoch() -> int:
    """当前时间戳（秒），给 order_no 生成用。"""
    return int(datetime.now().timestamp())
