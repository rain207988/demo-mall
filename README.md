# demo-mall 被测系统

> 三个测试项目的公共"靶子"：本地商城，含 **JWT 鉴权 API + 服务端渲染页面**。
> 设计目标：**零外部依赖**（无需 MySQL/Redis/Docker），clone 后 3 条命令跑起来，数据可一键重置。

## 快速启动

```bash
cd demo-mall
pip install -r requirements.txt
python seed.py --reset        # 初始化种子数据
python run.py                 # 默认 http://127.0.0.1:5000
```

验证：浏览器打开 http://127.0.0.1:5000/goods 应看到商品列表。

## 种子账号与数据

| 账号 | 密码 | 说明 |
|---|---|---|
| lemon | 123456 | 主测试账号 |
| test | 123456 | 数据驱动测试第二账号 |

商品 10 件（`seed.py` 里的 `SEED_GOODS`，id 1-10，价格/库存固定），
**测试框架的断言依赖这些确定性数据，改种子必须同步改测试的 data 目录。**

## 接口速查（完整字段见 docs/）

| 方法 | 路径 | 鉴权 | 业务码（失败时） |
|---|---|---|---|
| GET | /api/health | 无 | - |
| POST | /api/auth/register | 无 | 1003 重名 / 1004 参数 |
| POST | /api/auth/login | 无 | 1001 用户不存在 / 1002 密码错误 |
| GET | /api/auth/me | Bearer | 4010 |
| GET | /api/goods | 无 | 1004 参数错误 |
| GET | /api/goods/{id} | 无 | 2001 不存在 |
| GET | /api/cart | Bearer | 4010 |
| POST | /api/cart/items | Bearer | 2001 / 2002 库存不足 |
| PUT | /api/cart/items/{id} | Bearer | 3002 / 2002 |
| DELETE | /api/cart/items/{id} | Bearer | 3002 |
| POST | /api/orders | Bearer | 3001 购物车空 / 2001 / 2002 |
| GET | /api/orders | Bearer | - |
| GET | /api/orders/{id} | Bearer | 4001 |
| POST | /api/orders/{id}/pay | Bearer | 4002 状态不允许 |
| POST | /api/orders/{id}/cancel | Bearer | 4002 |
| POST | /api/test/reset | X-Test-Key | 403 |
| POST | /api/test/revoke-token | X-Test-Key | 403 |

响应统一包裹：`{"code": 0, "message": "ok", "data": {...}}`；
业务失败 HTTP 200 + code≠0，**鉴权失败 HTTP 401 + code 4010**（这是"三层断言"存在的原因，详见项目一文档）。

## 测试辅助接口（钥匙：`X-Test-Key: mall-test-key`）

```bash
# 一键重置数据（跑测试前必做，保证可重复）
curl -X POST http://127.0.0.1:5000/api/test/reset -H "X-Test-Key: mall-test-key"

# 吊销某个 token（练习"401→自动重登→重放"）
curl -X POST http://127.0.0.1:5000/api/test/revoke-token \
     -H "X-Test-Key: mall-test-key" -H "Content-Type: application/json" \
     -d '{"token": "<登录拿到的token>"}'
```

## 两种启动模式（性能压测对比用）

```bash
python run.py               # dev  模式：Flask 内置服务器（threaded=True）
python run.py --mode prod   # prod 模式：waitress 8 线程
```

perf-test 项目会分别压测两种模式，量化"换生产级 WSGI 服务器"的提升。

## 换成 MySQL

改 `app/db.py` 连接方式（pymysql + 连接参数），`schema.sql` 里
`INTEGER PRIMARY KEY AUTOINCREMENT` → `INT AUTO_INCREMENT PRIMARY KEY`，其余代码零改动。
