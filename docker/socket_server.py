#!/usr/bin/env python3
"""Small health/control socket shared by the compute and display services."""

import json
import os
import socket
import threading

path = os.environ.get("OP_SOCKET", "/run/openpilot/replay.sock")
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    os.unlink(path)
except FileNotFoundError:
    pass
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(path)
os.chmod(path, 0o666)
server.listen(8)

def handle(conn: socket.socket) -> None:
    with conn:
        request = json.loads(conn.recv(65536) or b"{}")
        response = {
            "ok": True,
            "service": "openpilot-compute",
            "request": request,
            "repo": "/opt/openpilot",
            "data_dir": os.environ.get("OP_DATA_DIR", "/data"),
        }
        conn.sendall((json.dumps(response) + "\n").encode())

while True:
    conn, _ = server.accept()
    threading.Thread(target=handle, args=(conn,), daemon=True).start()
