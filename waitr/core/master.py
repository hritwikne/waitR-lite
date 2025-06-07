import os
import sys
import signal
import socket

from waitr.core.worker import run_worker
from waitr.core.socket import send_fd_via_uds
from waitr.core.config import init_config, get_config

worker_pids = []
worker_channels = [] # [(pid, unix_socket)]

def handle_sigint(signum, frame):
    print(f"\n[Master] Received SIGINT. Shutting down workers...")
    
    for pid in worker_pids:
        print(f"[Master] Killing worker {pid}")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            print(f"[Master] Worker {pid} already exited")

    for pid in worker_pids:
        try:
            os.waitpid(pid, 0)
            print(f"[Master] Worker {pid} exited")
        except ChildProcessError:
            pass

    print("[Master] Shutdown complete.")
    sys.exit(0)

def start_workers(n):
    for _ in range(n):
        parent_sock, child_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)

        pid = os.fork()
        if (pid == 0):
            # worker process
            parent_sock.close()
            signal.signal(signal.SIGINT, signal.SIG_DFL) # remove sigint handler
            run_worker(child_sock)
            sys.exit(0)
        else:
            # master process
            print(f"[Master] Spawned worker PID {pid}")
            child_sock.close()
            worker_pids.append(pid)
            worker_channels.append((pid, parent_sock))

def start():
    print(f"[Master] PID {os.getpid()} starting")
    signal.signal(signal.SIGINT, handle_sigint)

    init_config()
    config = get_config()

    host = config['server']['host']
    port = config['server']['port']
    num_workers = config['server']['workers']

    # set up the server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen()
    print(f"[*] Server listening on {port}...")

    start_workers(num_workers)
    current_worker = 0

    while True:
        # Accept client connections
        client_sock, addr = server_socket.accept()
        pid, worker_sock = worker_channels[current_worker]

        print(f"[Master] Accepted connection from {addr}, sending to worker {pid}")
        
        send_fd_via_uds(worker_sock, client_sock.fileno()) # send to worker
        
        client_sock.close()
        current_worker = (current_worker + 1) % num_workers