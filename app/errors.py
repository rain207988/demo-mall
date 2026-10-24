"""统一响应封装 + 业务错误码字典。

设计决策：为什么业务失败也返回 HTTP 200，只用 code 区分？
- 国内大量系统（微信/支付宝开放平台等）都是"HTTP 层只表达传输是否成功，
  业务是否成功看 body 里的 code"；
- 这正好是接口自动化"三层断言"存在的理由：
  ①HTTP 状态码 ②业务 code ③关键字段——少一层都测不住。
- 鉴权类失败是例外：HTTP 401 + code 4010，因为它发生在"进入业务之前"。
"""

from flask import jsonify

# code: (默认 HTTP 状态码, 默认提示语)
BUSINESS_CODES = {
    0:    (200, "ok"),
    1001: (200, "用户不存在"),
    1002: (200, "密码错误"),
    1003: (200, "用户名已存在"),
    1004: (200, "参数缺失或格式错误"),
    2001: (200, "商品不存在或已下架"),
    2002: (200, "库存不足"),
    3001: (200, "购物车为空"),
    3002: (200, "购物车中不存在该商品"),
    4001: (200, "订单不存在"),
    4002: (200, "订单状态不允许该操作"),
    4010: (401, "未登录或 token 无效/过期"),
}


def ok(data=None):
    """业务成功：HTTP 200 + code 0。"""
    return jsonify({"code": 0, "message": "ok", "data": data}), 200


def fail(code: int, message: str = None, http_status: int = None):
    """业务失败：code 必须来自 BUSINESS_CODES，保证错误码不乱造。"""
    default_http, default_msg = BUSINESS_CODES[code]
    return jsonify({
        "code": code,
        "message": message or default_msg,
        "data": None,
    }), http_status or default_http


def auth_required_fail():
    """未登录/token 无效：HTTP 401 + 业务码 4010。

    测试框架会专门捕获这个响应用来练习"token 失效自动重登再重放"。
    """
    return fail(4010)
