"""Web 页面路由（服务端渲染，Flask session 鉴权）。

与 API 的关系：页面表单提交到这里，handler 调用与 API 相同的数据操作。
真实公司里"前端站 + 开放接口"也是这样两套入口共用一个服务层。

给 UI 自动化的约定（重要）：
- 所有可交互元素都有稳定 id 或 name，选择器不依赖样式类；
- 关键状态提示统一放 id="flash" 元素里，方便断言。
"""

from functools import wraps

from flask import Blueprint, render_template, request, redirect, session, flash, url_for

from app import db, auth

web_bp = Blueprint("web", __name__)


def web_login_required(view):
    """页面版登录拦截：未登录重定向到 /login?next=...，并带 flash 提示。"""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("请先登录")
            return redirect(url_for("web.login_page", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def _current_user():
    if not session.get("user_id"):
        return None
    return db.query_one("SELECT id, username, nickname FROM users WHERE id = ?", (session["user_id"],))


# ---------- 登录 / 登出 ----------

@web_bp.get("/login")
def login_page():
    return render_template("login.html", user=_current_user())


@web_bp.post("/login")
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = db.query_one("SELECT * FROM users WHERE username = ?", (username,))
    if not user or not auth.verify_password(password, user["password_hash"]):
        flash("用户名或密码错误")
        return redirect(url_for("web.login_page"))
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    next_url = request.args.get("next") or url_for("web.goods_page")
    return redirect(next_url)


@web_bp.post("/logout")
def logout():
    session.clear()
    flash("已退出登录")
    return redirect(url_for("web.login_page"))


# ---------- 商品 ----------

@web_bp.get("/")
def index():
    return redirect(url_for("web.goods_page"))


@web_bp.get("/goods")
def goods_page():
    keyword = (request.args.get("keyword") or "").strip()
    if keyword:
        rows = db.query_all(
            "SELECT id, name, price, stock FROM goods WHERE on_sale=1 AND name LIKE ? ORDER BY id",
            (f"%{keyword}%",),
        )
    else:
        rows = db.query_all("SELECT id, name, price, stock FROM goods WHERE on_sale=1 ORDER BY id")
    return render_template("goods.html", goods=rows, keyword=keyword, user=_current_user())


@web_bp.get("/goods/<int:goods_id>")
def goods_detail_page(goods_id: int):
    row = db.query_one("SELECT * FROM goods WHERE id = ? AND on_sale = 1", (goods_id,))
    if not row:
        flash("商品不存在或已下架")
        return redirect(url_for("web.goods_page"))
    return render_template("goods_detail.html", g=row, user=_current_user())


# ---------- 购物车 ----------

@web_bp.post("/cart/add")
@web_login_required
def cart_add():
    goods_id = int(request.form.get("goods_id", 0))
    quantity = int(request.form.get("quantity", 1))
    goods = db.query_one("SELECT * FROM goods WHERE id = ? AND on_sale=1", (goods_id,))
    if not goods:
        flash("商品不存在或已下架")
        return redirect(url_for("web.goods_page"))
    exist = db.query_one("SELECT * FROM cart_items WHERE user_id=? AND goods_id=?",
                         (session["user_id"], goods_id))
    new_qty = (exist["quantity"] if exist else 0) + quantity
    if new_qty > goods["stock"]:
        flash("库存不足")
        return redirect(request.referrer or url_for("web.goods_page"))
    if exist:
        db.get_db().execute("UPDATE cart_items SET quantity=? WHERE id=?", (new_qty, exist["id"]))
    else:
        db.get_db().execute("INSERT INTO cart_items(user_id, goods_id, quantity) VALUES(?,?,?)",
                            (session["user_id"], goods_id, quantity))
    db.get_db().commit()
    flash("已加入购物车")
    return redirect(request.referrer or url_for("web.goods_page"))


@web_bp.get("/cart")
@web_login_required
def cart_page():
    rows = db.query_all(
        "SELECT c.id, c.goods_id, g.name, g.price, c.quantity, g.stock "
        "FROM cart_items c JOIN goods g ON g.id=c.goods_id WHERE c.user_id=? ORDER BY c.id",
        (session["user_id"],),
    )
    total = round(sum(r["price"] * r["quantity"] for r in rows), 2)
    return render_template("cart.html", items=rows, total=total, user=_current_user())


@web_bp.post("/cart/update")
@web_login_required
def cart_update():
    item_id = int(request.form.get("item_id", 0))
    quantity = int(request.form.get("quantity", 1))
    item = db.query_one("SELECT c.*, g.stock FROM cart_items c JOIN goods g ON g.id=c.goods_id "
                        "WHERE c.id=? AND c.user_id=?", (item_id, session["user_id"]))
    if item and 1 <= quantity <= item["stock"]:
        db.get_db().execute("UPDATE cart_items SET quantity=? WHERE id=?", (quantity, item_id))
        db.get_db().commit()
        flash("数量已更新")
    else:
        flash("更新失败：数量非法或超出库存")
    return redirect(url_for("web.cart_page"))


@web_bp.post("/cart/delete")
@web_login_required
def cart_delete():
    item_id = int(request.form.get("item_id", 0))
    db.get_db().execute("DELETE FROM cart_items WHERE id=? AND user_id=?", (item_id, session["user_id"]))
    db.get_db().commit()
    flash("已删除")
    return redirect(url_for("web.cart_page"))


# ---------- 下单 / 订单 ----------

@web_bp.get("/checkout")
@web_login_required
def checkout_page():
    rows = db.query_all(
        "SELECT c.id, c.goods_id, g.name, g.price, c.quantity "
        "FROM cart_items c JOIN goods g ON g.id=c.goods_id WHERE c.user_id=? ORDER BY c.id",
        (session["user_id"],),
    )
    if not rows:
        flash("购物车为空，先去挑点东西吧")
        return redirect(url_for("web.goods_page"))
    total = round(sum(r["price"] * r["quantity"] for r in rows), 2)
    return render_template("checkout.html", items=rows, total=total, user=_current_user())


@web_bp.post("/checkout")
@web_login_required
def checkout_submit():
    """复用订单创建逻辑：与 API 相同的原子扣减/事务，防止并发超卖。"""
    rows = db.query_all(
        "SELECT c.goods_id, c.quantity, g.name, g.price, g.stock "
        "FROM cart_items c JOIN goods g ON g.id=c.goods_id WHERE c.user_id=?",
        (session["user_id"],),
    )
    if not rows:
        flash("购物车为空")
        return redirect(url_for("web.goods_page"))

    conn = db.get_db()
    merged: dict[int, int] = {}
    for r in rows:
        merged[r["goods_id"]] = merged.get(r["goods_id"], 0) + r["quantity"]
    for goods_id, quantity in merged.items():
        # 原子条件扣减：查库存+扣库存一步完成，行锁兜底并发；失败整体回滚
        dec = conn.execute("UPDATE goods SET stock = stock - ? WHERE id = ? AND stock >= ?",
                           (quantity, goods_id, quantity))
        if dec.rowcount == 0:
            conn.rollback()
            flash("库存不足，无法下单")
            return redirect(url_for("web.cart_page"))

    total = round(sum(r["price"] * r["quantity"] for r in rows), 2)
    order_no = auth.gen_order_no()
    try:
        cur = conn.execute(
            "INSERT INTO orders(order_no, user_id, total_amount, status) VALUES(?,?,?, 'pending')",
            (order_no, session["user_id"], total),
        )
        order_id = cur.lastrowid
        for r in rows:
            conn.execute("INSERT INTO order_items(order_id, goods_id, goods_name, price, quantity) "
                         "VALUES(?,?,?,?,?)", (order_id, r["goods_id"], r["name"], r["price"], r["quantity"]))
        conn.execute("DELETE FROM cart_items WHERE user_id = ?", (session["user_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        flash("下单失败，请重试")
        return redirect(url_for("web.cart_page"))
    flash(f"下单成功，订单号 {order_no}")
    return redirect(url_for("web.orders_page"))


@web_bp.get("/orders")
@web_login_required
def orders_page():
    rows = db.query_all(
        "SELECT id, order_no, total_amount, status, created_at FROM orders "
        "WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],),
    )
    return render_template("orders.html", orders=rows, user=_current_user())


@web_bp.post("/orders/<int:order_id>/pay")
@web_login_required
def order_pay(order_id: int):
    order = db.query_one("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, session["user_id"]))
    if not order or order["status"] != "pending":
        flash("订单状态不允许支付")
    else:
        conn = db.get_db()
        conn.execute("UPDATE orders SET status='paid', paid_at=datetime('now','localtime') WHERE id=?",
                     (order_id,))
        conn.commit()
        flash("支付成功")
    return redirect(url_for("web.orders_page"))


@web_bp.post("/orders/<int:order_id>/cancel")
@web_login_required
def order_cancel(order_id: int):
    order = db.query_one("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, session["user_id"]))
    if not order or order["status"] != "pending":
        flash("订单状态不允许取消")
    else:
        conn = db.get_db()
        items = db.query_all("SELECT goods_id, quantity FROM order_items WHERE order_id=?", (order_id,))
        for it in items:
            conn.execute("UPDATE goods SET stock = stock + ? WHERE id=?", (it["quantity"], it["goods_id"]))
        conn.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
        conn.commit()
        flash("订单已取消")
    return redirect(url_for("web.orders_page"))
