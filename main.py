#!/usr/bin/env python3
"""ShortM v02 — URL Fetch & Format Selection."""
import socket, threading, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uvicorn, webview
from api.routes import app

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

def wait_for_server(port, timeout=15):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1); return True
        except: time.sleep(0.3)
    return False

def main():
    port = find_free_port()
    threading.Thread(target=lambda: uvicorn.run(app, host="127.0.0.1", port=port, log_level="error"), daemon=True).start()
    if not wait_for_server(port): sys.exit(1)
    webview.create_window("ShortsM", f"http://127.0.0.1:{port}", width=1100, height=700, min_size=(800, 500))
    webview.start(debug=False)

if __name__ == "__main__":
    main()
