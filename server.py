#!/usr/bin/env python3
"""
EarthSystem — local application server.

Runs a small HTTP server from the Python standard library (no web framework
required), serving the browser interface from ./web and a JSON API backed by
the earthsys calculation package.

    python server.py                 # start and open a browser
    python server.py --port 8800     # choose the port
    python server.py --no-browser    # headless
"""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import os
import socket
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

BASE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BASE, "web")
PROJECTS = os.path.join(BASE, "projects")
OUTPUTS = os.path.join(BASE, "outputs")
sys.path.insert(0, BASE)

from earthsys import bem                                      # noqa: E402
from earthsys.api import (APP_VERSION, OUTPUTS, PROJECTS, ROUTES,  # noqa: E402
                          clean)




# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = f"EarthSystem/{APP_VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if os.environ.get("EARTHSYS_VERBOSE"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # -- helpers ----------------------------------------------------------
    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8",
              extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code, payload):
        self._send(code, json.dumps(clean(payload), ensure_ascii=False,
                                    allow_nan=False).encode("utf-8"))

    # -- routing ----------------------------------------------------------
    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/api/meta", "/api/project/list"):
            try:
                self._json(200, ROUTES[path]({}))
            except Exception as exc:
                self._json(500, dict(error=str(exc)))
            return
        if path == "/api/health":
            self._json(200, dict(ok=True, version=APP_VERSION,
                                 numpy=bem.HAVE_NUMPY))
            return
        if path.startswith("/outputs/"):
            return self._static(OUTPUTS, path[len("/outputs/"):])
        if path.startswith("/docs/"):
            return self._static(os.path.join(BASE, "docs"), path[len("/docs/"):])
        if path == "/":
            path = "/index.html"
        self._static(WEB, path.lstrip("/"))

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        fn = ROUTES.get(path)
        if not fn:
            return self._json(404, dict(error=f"Unknown endpoint {path}"))
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:
            return self._json(400, dict(error=f"Bad JSON: {exc}"))
        try:
            self._json(200, fn(payload))
        except Exception as exc:
            if os.environ.get("EARTHSYS_VERBOSE"):
                traceback.print_exc()
            self._json(400, dict(error=str(exc),
                                 type=type(exc).__name__,
                                 trace=traceback.format_exc().splitlines()[-4:]))

    def _static(self, root, rel):
        rel = rel.replace("\\", "/")
        full = os.path.normpath(os.path.join(root, rel))
        if not full.startswith(os.path.normpath(root)) or not os.path.isfile(full):
            return self._send(404, b"Not found", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",
                                                  "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as fh:
            self._send(200, fh.read(), ctype)


def free_port(preferred=8765):
    for port in [preferred] + list(range(preferred + 1, preferred + 40)):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def serve(port=None, open_browser=True, quiet=False):
    port = port or free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    if not quiet:
        print("=" * 62)
        print(f"  EarthSystem {APP_VERSION} — earthing system design")
        print(f"  Open in your browser:  {url}")
        np_state = "yes" if bem.HAVE_NUMPY else "NO — numerical solver disabled"
        print("  numpy available: " + np_state)
        print("  Press Ctrl+C to stop.")
        print("=" * 62)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
    return url


def main():
    ap = argparse.ArgumentParser(description="EarthSystem local server")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    serve(a.port, not a.no_browser, a.quiet)


if __name__ == "__main__":
    main()
