import os
import socket
from waitr.core.config import init_config, get_config

worker_pids = []

def start_workers(n):
    for _ in range(n):
        pid = os.fork()
        if (pid == 0):
            # worker process
            print('child spawned')
        else:
            # master process
            worker_pids.append(pid)

def start():
    init_config()
    config = get_config()

    host = config['server']['host']
    port = config['server']['port']

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)

    print(f"Server listening on {host}:{port}")

    num_workers = config['server']['workers']
    start_workers(num_workers)