import os
import sys
import socket
import signal
import time
import selectors

from waitr.core.socket import recv_fd_from_uds
from waitr.http.parser import parse_request
from waitr.http.static_handler import serve_static_file

selector = selectors.DefaultSelector()
active_connections = {} # sock: {'last_active': timestamp, 'keep_alive': bool}

IDLE_TIMEOUT = 10 # seconds

def close_connection(sock):
    selector.unregister(sock)
    sock.close()
    active_connections.pop(sock, None)
    print(f"[Worker {os.getpid()}] Closed connection")

def handle_client(sock, mask):
    try:
        data = sock.recv(4096)
        if not data:
            close_connection(sock)
            return
        
        headers = parse_request(data)
        method, path, version = headers[0].strip().split(' ')
        conn_header = [h for h in headers if h.lower().startswith('connection:')]
        keep_alive = True if version == 'HTTP/1.1' else False

        if conn_header:
            if 'close' in conn_header[0].lower():
                keep_alive = False
        
        if method == 'GET':
            serve_static_file(sock, path)

        active_connections[sock]['last_active'] = time.time()
        active_connections[sock]['keep_alive'] = keep_alive

        if not keep_alive:
            close_connection(sock)
    
    except Exception as e:
        print(f"Error: {e}")
        close_connection(sock)

def handle_msg_receive(unix_sock, mask):
    client_fd = recv_fd_from_uds(unix_sock)
    if client_fd != -1:
        client_sock = socket.socket(fileno=client_fd)
        client_sock.setblocking(False)
        selector.register(client_sock, selectors.EVENT_READ, handle_client)

        active_connections[client_sock] = {
            'last_active': time.time(),
            'keep_alive': True
        }

        print(f"[Worker {os.getpid()}] Got client FD {client_fd}")

def run_worker(unix_sock):
    print(f"[Worker] PID {os.getpid()} started")

    # handling terminate signal from master process
    def handle_sigterm(signum, frame):
        print(f"[Worker] PID {os.getpid()} shutting down...")
        sys.exit(0)
    signal.signal(signal.SIGTERM, handle_sigterm)

    selector.register(unix_sock, selectors.EVENT_READ, handle_msg_receive)
    print(f"[Worker {os.getpid()}] Event loop running...")

    # main event loop
    while True:
        events = selector.select(timeout=5) # 5s timeout to perform other operations

        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)
        
        now = time.time()

        # close any idle connections
        for sock, info in list(active_connections.items()):
            if now - info['last_active'] > IDLE_TIMEOUT:
                print(f"[Worker {os.getpid()}] Closing idle connection")
                close_connection(sock)