#!/usr/bin/env python3
# Earthing System — earthing system design to IEEE 80, IEC 60364, IEC 62305 and IEEE 142.
# Copyright (C) 2026 Emad Roshandel
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.

"""
Earthing System — desktop mode.

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
    print(f"Earthing System {server.APP_VERSION} — {url}")

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
        f"Earthing System {server.APP_VERSION} — Earthing System Design",
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
