import os
import sys
import json
import importlib
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

PORT = int(os.environ.get("ANTIGRAVITY_SIDECAR_WEB_PORT") or 5901)

# 动态热加载内核
_ENGINE_MTIME = 0
_ENGINE_MODULE = None

def get_engine(force_reload=False):
    global _ENGINE_MTIME, _ENGINE_MODULE
    engine_file = os.path.join(os.path.dirname(__file__), "engine.py")
    current_mtime = os.path.getmtime(engine_file) if os.path.exists(engine_file) else 0

    if force_reload or _ENGINE_MODULE is None or current_mtime > _ENGINE_MTIME:
        importlib.invalidate_caches()
        if "engine" in sys.modules:
            _ENGINE_MODULE = importlib.reload(sys.modules["engine"])
        else:
            sys.path.insert(0, os.path.dirname(__file__))
            import engine
            _ENGINE_MODULE = engine
        _ENGINE_MTIME = current_mtime
    return _ENGINE_MODULE

class ContextHUDHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/restart":
            self.handle_restart()
        else:
            self.send_response(404)
            self.end_headers()

    def handle_restart(self):
        """
        完整真重启：
        1. 强制热重载 engine.py 模块，100% 重新加载磁盘上的最新 Python 代码
        2. 清理临时 SQLite 数据库连接与内存状态缓存
        3. 保持当前已分配端口不变，避免 Electron iframe 因端口变更断连
        4. 前端收到 200 响应后硬刷新页面，重读最新 index.html 与重拉全量数据
        """
        try:
            engine = get_engine(force_reload=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "reloaded": True,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": "服务内核代码与状态已完整重载！"
            }, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ["/", "/index.html"]:
            html_path = os.path.join(os.path.dirname(__file__), "index.html")
            if os.path.exists(html_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(html_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"index.html not found")

        elif path == "/api/restart":
            self.handle_restart()

        elif path == "/api/active-context":
            cid = query.get("cid", [None])[0]
            tracked_cid = query.get("tracked_cid", [None])[0]
            engine = get_engine()
            data = engine.get_conversation_context_details(target_cid=cid, current_tracked_cid=tracked_cid)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

        elif path == "/api/conversations":
            engine = get_engine()
            convs = engine.get_conversations_list(limit=50)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"conversations": convs}, ensure_ascii=False).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=PORT):
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("127.0.0.1", port), ContextHUDHandler)
    print("======================================================", flush=True)
    print(" Antigravity Context HUD Service Started!", flush=True)
    print(f" Web URL: http://127.0.0.1:{port}/ (ENV PORT: {os.environ.get('ANTIGRAVITY_SIDECAR_WEB_PORT')})", flush=True)
    print("======================================================", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nService stopped.", flush=True)
        server.server_close()

if __name__ == "__main__":
    run_server()
