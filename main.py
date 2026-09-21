#!/usr/bin/env python3
"""ShortsM — AI Shorts Generator Desktop Launcher."""
import os
import sys
import time
import socket
import threading
import logging

# Filter out snap paths from LD_LIBRARY_PATH to avoid glibc / libpthread version conflicts
if "LD_LIBRARY_PATH" in os.environ:
    clean_paths = [p for p in os.environ["LD_LIBRARY_PATH"].split(":") if "snap" not in p and p]
    os.environ["LD_LIBRARY_PATH"] = ":".join(clean_paths)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
import webview
from api.routes import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def wait_for_server(port, timeout=15):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False

def start_gui(url):
    """Launch GUI with PyQt6 engine to prevent WebKitGTK snap library collisions."""
    try:
        webview.create_window(
            "ShortsM",
            url,
            width=1100,
            height=700,
            min_size=(800, 500)
        )
        webview.start(gui="qt", debug=False)
        return
    except Exception as e:
        print(f"[ShortsM] Webview window error: {e}")

    # Fallback to system browser
    print(f"[ShortsM] Opening in default browser at {url}")
    import webbrowser
    webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[ShortsM] Exiting...")

def main():
    port = find_free_port()
    server_url = f"http://127.0.0.1:{port}"
    print(f"[ShortsM] Starting backend server at {server_url} ...")

    t = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=port, log_level="info"),
        daemon=True
    )
    t.start()

    if not wait_for_server(port):
        print("[ShortsM] Error: Server failed to start.")
        sys.exit(1)

    print(f"[ShortsM] Server is ready at {server_url}")
    start_gui(server_url)

if __name__ == "__main__":
    main()
