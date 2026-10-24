"""demo-mall 启动入口。

两种模式（性能压测对比的关键）：
    python run.py                 # dev：Flask 内置服务器（threaded=True）
    python run.py --mode prod     # prod：waitress 8 线程，生产级 WSGI
    python run.py --port 5001     # 换端口
"""

import argparse

from config import HOST, PORT


def main():
    parser = argparse.ArgumentParser(description="demo-mall 被测系统")
    parser.add_argument("--mode", choices=["dev", "prod"], default="dev",
                        help="dev=Flask内置服务器 / prod=waitress多线程")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    from app import create_app
    app = create_app()

    if args.mode == "dev":
        print(f"[demo-mall] dev 模式 http://{HOST}:{args.port} （Flask 内置服务器）")
        # threaded=True：允许多线程并发处理请求，否则压测时请求会排队
        app.run(host=HOST, port=args.port, debug=False, threaded=True)
    else:
        from waitress import serve
        print(f"[demo-mall] prod 模式 http://{HOST}:{args.port} （waitress 8 线程）")
        serve(app, host=HOST, port=args.port, threads=8)


if __name__ == "__main__":
    main()
