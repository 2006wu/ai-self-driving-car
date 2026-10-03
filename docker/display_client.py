#!/usr/bin/env python3
"""Health check client for the compute container's Unix socket."""

import json
import os
import socket

SOCKET_PATH = os.environ.get("OP_SOCKET", "/run/openpilot/replay.sock")
REQUEST = {"op": "health", "client": "display"}


def main() -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(SOCKET_PATH)
        sock.sendall(json.dumps(REQUEST).encode())
        response = json.loads(sock.recv(65536).decode())

    if response.get("ok") is not True:
        raise RuntimeError(response)
    print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
