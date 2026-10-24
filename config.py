"""demo-mall 全局配置。

为什么单独一个 config.py：
1. 端口、Token 有效期、测试密钥这类"会变的数"不散落在代码里，改一处即可；
2. 测试框架的 config/config.yaml 与这里是"镜像关系"——两边对齐，链路才通。
"""

HOST = "127.0.0.1"
PORT = 5000

# JWT 配置（仅演示用，生产环境绝不许硬编码 secret）
JWT_SECRET = "demo-mall-secret-key-change-me"
TOKEN_EXPIRE_SECONDS = 1800          # token 有效期 30 分钟，用于练习"过期/失效重新登录"

# 测试辅助接口的钥匙：请求头 X-Test-Key 必须带上它才能调用 /api/test/*
# 真实项目里等价物是"测试环境的 admin token / 运维白名单"，这里简化成一个固定值
TEST_KEY = "mall-test-key"

# SQLite 数据库文件位置（与 app 包同级）
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "demo_mall.db")
