"""购物车接口：查/加/改/删。所有接口都要求登录（token 关联练习的核心场景）。"""

from flask import Blueprint, request

from app import db, auth
from app.errors import ok, fail

cart_bp = Blueprint("cart_api", __name__, url_prefix="/api/cart")


@cart_bp.get("")
@auth.login_required
def my_cart(payload):
    """GET /api/cart —— 返回当前用户购物车明细与合计金额。"""
    rows = db.query_all(
        "SELECT c.id, c.goods_id, g.name, g.price, g.stock, c.quantity "
        "FROM cart_items c JOIN goods g ON g.id = c.goods_id "
        "WHERE c.user_id = ? ORDER BY c.id",
        (payload["user_id"],),
    )
    items = [dict(r) for r in rows]
    total = round(sum(i["price"] * i["quantity"] for i in items), 2)
    return ok({"items": items, "total_amount": total, "count": len(items)})


@cart_bp.post("/items")
@auth.login_required
def add_item(payload):
    """POST /api/cart/items  body: {"goods_id": 1, "quantity": 2}

    同一商品重复加购 → 数量累加；库存校验放在"加购"这一步就做，
    提前暴露问题比下单时才发现体验好（这是业务设计，不是 bug）。
    """
    body = request.get_json(silent=True) or {}
    goods_id, quantity = body.get("goods_id"), body.get("quantity", 1)
    if not isinstance(goods_id, int) or not isinstance(quantity, int) or quantity < 1:
        return fail(1004)

    goods = db.query_one("SELECT * FROM goods WHERE id = ? AND on_sale = 1", (goods_id,))
    if not goods:
        return fail(2001)

    conn = db.get_db()
    exist = db.query_one(
        "SELECT * FROM cart_items WHERE user_id = ? AND goods_id = ?",
        (payload["user_id"], goods_id),
    )
    new_qty = (exist["quantity"] if exist else 0) + quantity
    if new_qty > goods["stock"]:
        return fail(2002, f"库存不足：当前库存 {goods['stock']}，购物车将持有 {new_qty}")

    if exist:
        conn.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (new_qty, exist["id"]))
    else:
        conn.execute(
            "INSERT INTO cart_items(user_id, goods_id, quantity) VALUES(?,?,?)",
            (payload["user_id"], goods_id, quantity),
        )
    conn.commit()
    return ok({"goods_id": goods_id, "quantity": new_qty})


@cart_bp.put("/items/<int:item_id>")
@auth.login_required
def update_item(item_id: int, payload):
    """PUT /api/cart/items/<id>  body: {"quantity": 3} —— 修改数量。"""
    body = request.get_json(silent=True) or {}
    quantity = body.get("quantity")
    if not isinstance(quantity, int) or quantity < 1:
        return fail(1004, "quantity 必须是正整数")

    item = db.query_one(
        "SELECT c.*, g.stock FROM cart_items c JOIN goods g ON g.id = c.goods_id "
        "WHERE c.id = ? AND c.user_id = ?",
        (item_id, payload["user_id"]),
    )
    if not item:
        return fail(3002)
    if quantity > item["stock"]:
        return fail(2002)

    conn = db.get_db()
    conn.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (quantity, item_id))
    conn.commit()
    return ok({"item_id": item_id, "quantity": quantity})


@cart_bp.delete("/items/<int:item_id>")
@auth.login_required
def delete_item(item_id: int, payload):
    item = db.query_one(
        "SELECT id FROM cart_items WHERE id = ? AND user_id = ?",
        (item_id, payload["user_id"]),
    )
    if not item:
        return fail(3002)
    conn = db.get_db()
    conn.execute("DELETE FROM cart_items WHERE id = ?", (item_id,))
    conn.commit()
    return ok({"item_id": item_id})
