import os
from waitr.core.config import get_config

def serve_static_file(path):
    config = get_config()
    static_root = config['static']['root']
    static_index = config['static']['index']

    if path == '/':
        path = '/' + static_index

    full_path = os.path.join(static_root, path.lstrip("/"))

    if not os.path.isfile(full_path):
        body = b"Not Found"
        headers = (
            f"HTTP/1.1 404 Not Found\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Content-Type: text/plain\r\n"
            f"\r\n"
        ).encode()
        return headers + body

    with open(full_path, "rb") as f:
        body = f.read()

    headers = (
        f"HTTP/1.1 200 OK\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Content-Type: text/html\r\n"
        f"\r\n"
    ).encode()

    return headers + body
