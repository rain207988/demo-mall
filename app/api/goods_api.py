"""商品接口：列表(分页/搜索) + 详情。压测和 UI 搜索用例的主战场。"""

from flask import Blueprint, request

from app import db
from app.errors import ok, fail

goods_bp = Blueprint("goods_api", __name__, url_prefix="/api/goods")


@goods_bp.get("")
def list_goods():
    """GET /api/goods?page=1&page_size=5&keyword=蓝牙&category=手机数码

    查询类接口：参数全部走 query string，返回固定分页结构
    data: {list, total, page, page_size} —— 分页断言练习的标准样本。
    """
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(50, max(1, int(request.args.get("page_size", 5))))
    except ValueError:
        return fail(1004, "page/page_size 必须是整数")

    keyword = (request.args.get("keyword") or "").strip()
    category = (request.args.get("category") or "").strip()

    where, args = "on_sale = 1", []
    if keyword:
        where += " AND name LIKE ?"
        args.append(f"%{keyword}%")
    if category:
        where += " AND category = ?"
        args.append(category)

    total = db.query_one(f"SELECT COUNT(*) AS c FROM goods WHERE {where}", tuple(args))["c"]
    rows = db.query_all(
        f"SELECT id, name, category, price, stock, description FROM goods "
        f"WHERE {where} ORDER BY id LIMIT ? OFFSET ?",
        tuple(args) + (page_size, (page - 1) * page_size),
    )
    return ok({
        "list": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@goods_bp.get("/<int:goods_id>")
def goods_detail(goods_id: int):
    row = db.query_one(
        "SELECT id, name, category, price, stock, description FROM goods WHERE id = ? AND on_sale = 1",
        (goods_id,),
    )
    if not row:
        return fail(2001)
    return ok(dict(row))
