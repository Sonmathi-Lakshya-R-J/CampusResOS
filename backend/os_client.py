import os
import socket

SOCKET_PATH = os.getenv("CAMPUSRESOS_SOCKET", "/tmp/campusresos.sock")

def worker_command(command: str, timeout: float = 2.0) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(SOCKET_PATH)
        client.sendall((command.strip() + "\n").encode("utf-8"))
        data = b""
        while b"\n" not in data and len(data) < 8192:
            chunk = client.recv(1024)
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8", errors="replace").strip()

def worker_status():
    try:
        return {"available": True, "reply": worker_command("PING")}
    except (OSError, TimeoutError) as exc:
        return {"available": False, "error": str(exc)}
