import os
import sys
import signal
import socket
import logging
from cachetools import TTLCache

from waitr.core.uds import send_fd_via_uds
from waitr.core.config import init_config, get_config
from waitr.core.worker import run_worker

current_worker = 0
worker_channels = [] # (pid, uds_write_end)

ip_worker_cache = TTLCache(maxsize=100, ttl=30)
logger = logging.getLogger('waitr.core.master')

def handle_sigint(signum, frame):
    logger.info("[M] Received SIGINT. Shutting down workers...")
    
    for (pid, _) in worker_channels:
        logger.info(f"[M] Killing worker {pid}..")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            logger.info(f"[M] Worker {pid} already exited")

    for (pid, _) in worker_channels:
        try:
            os.waitpid(pid, 0)
            logger.info(f"[M] Worker {pid} exited")
        except ChildProcessError:
            pass

    logger.info("[M] Shutdown complete. Exiting..")
    sys.exit(0)

def start_workers(n, server_socket):
    logger.debug("[M] Forking worker processes..")
    for i in range(n):
        parent_sock, child_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        logger.debug(f"[M] UDS Socketpair {(i + 1)} created.")

        pid = os.fork()
        if (pid == 0):
            # worker process
            logger.debug("Closing unused fds inherited from master")
            server_socket.close()
            parent_sock.close()
            for other_pid, other_sock in worker_channels:
                # uds write-end fd of previously spawned workers
                other_sock.close() 
            logger.debug("Closed unused fd's")

            signal.signal(signal.SIGINT, signal.SIG_DFL) # remove sigint handler inherited from master
            run_worker(child_sock)
            sys.exit(0)
        else:
            # master process
            logger.info(f"[M] Spawned worker PID {pid}")
            child_sock.close()
            worker_channels.append((pid, parent_sock))

def assign_worker_for_ip(ip):
    global current_worker
    cached = ip_worker_cache.get(ip)

    if cached:
        logger.debug(f"Cache hit: Reusing worker {cached[0]} for IP {ip}")
        return cached
    
    worker = worker_channels[current_worker]
    logger.debug(f"Cache miss: Assigning new worker {worker[0]} to IP {ip}")
    ip_worker_cache[ip] = worker
    current_worker = (current_worker + 1) % len(worker_channels)
    return worker

def start():
    logger.info("[M] Master process started execution")
    signal.signal(signal.SIGINT, handle_sigint)

    init_config()
    config = get_config()

    host = config['server']['host']
    port = config['server']['port']
    num_workers = config['server']['workers']

    logger.debug("[M] Trying to create/bind/listen socket..")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen()

    logger.info(f"[M] WaitR Lite Server listening on PORT {port}")

    start_workers(num_workers, server_socket)
    global ip_worker_cache

    while True:
        logger.info("[M] Ready to accept new connections")
        client_sock, addr = server_socket.accept()
        
        client_ip = addr[0]
        pid, unix_sock = assign_worker_for_ip(client_ip)

        logger.info(f"[M] Accepted connection from {addr}, sending to Worker {pid}")
        send_fd_via_uds(unix_sock, client_sock.fileno())
        client_sock.close()
