import socket
import threading
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
import webview
from api.routes import app


# port find function
def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:  # Fixed AF_INET
        s.bind(("127.0.0.1", 0))  # Fixed tuple requirement
        return s.getsockname()[1]


# wait for server
def wait_for_server(port: int, timeout: int = 15) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
            return True
        except:
            time.sleep(0.3)
    return False


def main():
    port = find_free_port()
    print(f"Running on port {port}")

    threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=port, log_level="error"),
        daemon=True,  # Fixed spelling of daemon
    ).start()

    if not wait_for_server(port):
        print("Server unavailable", file=sys.stderr)
        sys.exit(1)

    print("Server Ready")

    # If it throws an error, simply remove it.
    webview.create_window(
        title="ShortsM",
        url=f"http://127.0.0.1:{port}/",
        width=1100,
        height=700,
        min_size=(800, 500),
    )
    webview.start(debug=False)


# Fixed indentation so the script actually executes
if __name__ == "__main__":
    main()