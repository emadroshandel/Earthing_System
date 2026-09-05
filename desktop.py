#!/usr/bin/env python3
"""
EarthSystem — desktop mode.

Starts the local server in a background thread and shows the interface in a
native application window using pywebview.  If pywebview is not installed the
application falls back to the default web browser, so this entry point always
works:

    python desktop.py
    pip install pywebview      # optional, for the native window
"""

from __future__ import annotations

import sys
import threading
import time

import server


def main():
    port = server.free_port(8765)
    httpd_holder = {}

    def run_server():
        from http.server import ThreadingHTTPServer
        httpd = ThreadingHTTPServer(("127.0.0.1", port), server.Handler)
        httpd_holder["s"] = httpd
        httpd.serve_forever()

    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(0.6)
    url = f"http://127.0.0.1:{port}/"
    print(f"EarthSystem {server.APP_VERSION} — {url}")

    try:
        import webview                                   # type: ignore
    except ImportError:
        print("pywebview is not installed — opening the default browser instead.")
        print("For a native desktop window:  pip install pywebview")
        import webbrowser
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped.")
        return

    webview.create_window(
        f"EarthSystem {server.APP_VERSION} — Earthing System Design",
        url, width=1500, height=950, min_size=(1100, 700), confirm_close=False)
    try:
        webview.start()
    finally:
        s = httpd_holder.get("s")
        if s:
            s.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    main()
