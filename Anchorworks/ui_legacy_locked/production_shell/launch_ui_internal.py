# AnchorWorks - Internal UI Server
# DO NOT RUN DIRECTLY - Use ui/launch_ui.py instead

import http.server
import json
import os
import socketserver
import ssl
import sys
from urllib.parse import unquote

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Resolve host + TLS from anchorworks.config.json (same as bridge/llm servers)
_UI_HOST = "127.0.0.1"
_UI_TLS = False
try:
    _base = os.path.dirname(DIRECTORY)
    if _base not in sys.path:
        sys.path.insert(0, _base)
    _plugins = os.path.join(_base, "plugins")
    if _plugins not in sys.path:
        sys.path.insert(0, _plugins)
    from security.data_paths import ANCHORWORKS_CONFIG_PATH
    from security.secure_storage import secure_json_load
    _ui_cfg = secure_json_load(ANCHORWORKS_CONFIG_PATH).get("server", {})
    _UI_HOST = _ui_cfg.get("host", "127.0.0.1")
    _UI_TLS = _ui_cfg.get("tls", False)
except Exception:
    pass

# Static assets: keep in-memory after first read to avoid repeated disk I/O
_file_cache = {}  # abs_path -> (mtime, content_type, bytes)


class UIRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def translate_path(self, path):
        # Allow UI to reference /ART/* assets directly from repository ART directory.
        if path.startswith("/ART/"):
            repo_root = os.path.dirname(DIRECTORY)
            art_root = os.path.join(repo_root, "ART")
            rel = unquote(path.split("?", 1)[0]).replace("\\", "/")
            rel = rel[len("/ART/"):]
            safe_rel = os.path.normpath(rel).lstrip("\\/")
            candidate = os.path.abspath(os.path.join(art_root, safe_rel))
            if os.path.commonpath([os.path.abspath(art_root), candidate]) == os.path.abspath(art_root):
                return candidate
            return os.path.join(art_root, "__invalid__")
        return super().translate_path(path)

    def do_GET(self):
        req_path = self.path.split("?", 1)[0]
        if req_path == "/" or req_path == "":
            self.send_response(302)
            self.send_header("Location", "/anchorworks_production.html")
            self.end_headers()
            return
        # Backward-compat redirect for older production-page names.
        if req_path.endswith("_ai_production.html") and req_path != "/anchorworks_production.html":
            self.send_response(302)
            self.send_header("Location", "/anchorworks_production.html")
            self.end_headers()
            return

        # Serve from memory cache for known static files
        ext = os.path.splitext(req_path)[1].lower()
        if ext in ('.html', '.css', '.js', '.json', '.svg'):
            return self._serve_cached()

        super().do_GET()

    def _serve_cached(self):
        path = self.translate_path(self.path)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            self.send_error(404)
            return

        cached = _file_cache.get(path)
        if cached and cached[0] == mtime:
            ctype, content = cached[1], cached[2]
        else:
            try:
                with open(path, 'rb') as f:
                    content = f.read()
            except (FileNotFoundError, IsADirectoryError):
                self.send_error(404)
                return
            ctype = self.guess_type(path)
            _file_cache[path] = (mtime, ctype, content)

        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()


if __name__ == "__main__":
    protocol = "https" if _UI_TLS else "http"
    print(f"Serving UI from {DIRECTORY} on {protocol}://{_UI_HOST}:{PORT}")

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((_UI_HOST, PORT), UIRequestHandler) as httpd:
        if _UI_TLS:
            try:
                from security.tls import ensure_tls
                tls_result = ensure_tls()
                if tls_result:
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    ctx.load_cert_chain(certfile=tls_result[0], keyfile=tls_result[1])
                    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
                    print(f"TLS enabled: {tls_result[0]}")
            except Exception as e:
                print(f"TLS setup failed, serving plain HTTP: {e}")
        httpd.serve_forever()
