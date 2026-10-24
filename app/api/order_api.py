"""订单接口：创建(从购物车/直购)、列表、详情、支付、取消。

这是"上下游关联"教学的主战场：
create 返回 data.order_id / data.order_no，后续接口全靠它串起来。
"""

import random

from flask import Blueprint, request

from app import db, auth
from app.errors import ok, fail
from app.auth import current_epoch

order_bp = Blueprint("order_api", __name__, url_prefix="/api/orders")


@order_bp.post("")
@auth.login_required
def create_order(payload):
    """POST /api/orders
    body 二选一：
      {"from_cart": true}                     —— 清空购物车生成订单
      {"items": [{"goods_id":1,"quantity":2}]} —— 直购
    成功返回 data: {order_id, order_no, total_amount, status}
    """
    body = request.get_json(silent=True) or {}
    user_id = payload["user_id"]
    conn = db.get_db()

    # ① 准备"要买的商品清单"
    if body.get("from_cart"):
        cart_rows = db.query_all(
            "SELECT c.goods_id, c.quantity, g.name, g.price, g.stock "
            "FROM cart_items c JOIN goods g ON g.id = c.goods_id WHERE c.user_id = ?",
            (user_id,),
        )
        if not cart_rows:
            return fail(3001)
        buy_list = [dict(r) for r in cart_rows]
    else:
        raw_items = body.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            return fail(1004)
        buy_list = []
        for it in raw_items:
            goods_id, quantity = it.get("goods_id"), it.get("quantity", 1)
            if not isinstance(goods_id, int) or not isinstance(quantity, int) or quantity < 1:
                return fail(1004)
            goods = db.query_one(
                "SELECT id, name, price, stock FROM goods WHERE id = ? AND on_sale = 1", (goods_id,)
            )
            if not goods:
                return fail(2001, f"商品 {goods_id} 不存在或已下架")
            buy_list.append({"goods_id": goods_id, "quantity": quantity,
                             "name": goods["name"], "price": goods["price"], "stock": goods["stock"]})

    # ② 库存校验（同一商品在清单里出现多次时合并数量）
    merged: dict[int, int] = {}
    for item in buy_list:
        merged[item["goods_id"]] = merged.get(item["goods_id"], 0) + item["quantity"]
    for goods_id, quantity in merged.items():
        stock = db.query_one("SELECT stock FROM goods WHERE id = ?", (goods_id,))["stock"]
        if quantity > stock:
            return fail(2002, f"商品 {goods_id} 库存不足：需 {quantity}，存 {stock}")

    # ③ 事务：扣库存 + 建订单 + 建订单明细 + (清购物车)，任一步失败全部回滚
    total = round(sum(i["price"] * i["quantity"] for i in buy_list), 2)
    order_no = f"ORD{current_epoch()}{random.randint(100, 999)}"
    try:
        cur = conn.execute(
            "INSERT INTO orders(order_no, user_id, total_amount, status) VALUES(?,?,?, 'pending')",
            (order_no, user_id, total),
        )
        order_id = cur.lastrowid
        for item in buy_list:
            conn.execute(
                "INSERT INTO order_items(order_id, goods_id, goods_name, price, quantity) VALUES(?,?,?,?,?)",
                (order_id, item["goods_id"], item["name"], item["price"], item["quantity"]),
            )
            conn.execute("UPDATE goods SET stock = stock - ? WHERE id = ?",
                         (item["quantity"], item["goods_id"]))
        if body.get("from_cart"):
            conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return ok({"order_id": order_id, "order_no": order_no, "total_amount": total, "status": "pending"})


@order_bp.get("")
@auth.login_required
def my_orders(payload):
    """GET /api/orders?status=pending —— 当前用户订单列表（不传 status 返回全部）。"""
    status = (request.args.get("status") or "").strip()
    sql = ("SELECT id, order_no, total_amount, status, created_at FROM orders "
           "WHERE user_id = ?")
    args: list = [payload["user_id"]]
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY id DESC"
    rows = db.query_all(sql, tuple(args))
    return ok({"list": [dict(r) for r in rows], "total": len(rows)})


@order_bp.get("/<int:order_id>")
@auth.login_required
def order_detail(order_id: int, payload):
    """GET /api/orders/<id> —— 详情含明细；查别人的订单也是 4001（不泄露存在性）。"""
    order = db.query_one(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, payload["user_id"])
    )
    if not order:
        return fail(4001)
    items = db.query_all(
        "SELECT goods_id, goods_name, price, quantity FROM order_items WHERE order_id = ?",
        (order_id,),
    )
    data = dict(order)
    data["items"] = [dict(r) for r in items]
    return ok(data)


@order_bp.post("/<int:order_id>/pay")
@auth.login_required
def pay_order(order_id: int, payload):
    """POST /api/orders/<id>/pay —— pending → paid。重复支付/已取消订单 → 4002。"""
    order = db.query_one(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, payload["user_id"])
    )
    if not order:
        return fail(4001)
    if order["status"] != "pending":
        return fail(4002, f"当前状态 {order['status']} 不允许支付")
    conn = db.get_db()
    conn.execute("UPDATE orders SET status = 'paid', paid_at = datetime('now','localtime') WHERE id = ?",
                 (order_id,))
    conn.commit()
    return ok({"order_id": order_id, "status": "paid"})


@order_bp.post("/<int:order_id>/cancel")
@auth.login_required
def cancel_order(order_id: int, payload):
    """POST /api/orders/<id>/cancel —— pending → cancelled，并把库存加回去。"""
    order = db.query_one(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, payload["user_id"])
    )
    if not order:
        return fail(4001)
    if order["status"] != "pending":
        return fail(4002, f"当前状态 {order['status']} 不允许取消")
    conn = db.get_db()
    items = db.query_all("SELECT goods_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
    for it in items:
        conn.execute("UPDATE goods SET stock = stock + ? WHERE id = ?", (it["quantity"], it["goods_id"]))
    conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    conn.commit()
    return ok({"order_id": order_id, "status": "cancelled"})
