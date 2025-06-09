import os
import sys
import socket
import signal
import time
import selectors
import logging

from waitr.core.config import get_config
from waitr.core.uds import recv_fd_from_uds
from waitr.http.parser import parse_request, is_full_http_request
from waitr.http.static_handler import serve_static_file
from waitr.http.proxy import proxy_to_upstream, match_proxy_route

IDLE_TIMEOUT = 60  # seconds
active_connections = {} # sock: conn_state

selector = selectors.DefaultSelector()
logger = logging.getLogger('waitr.core.worker')

def close_connection(sock: socket.socket) -> None:
    try:
        selector.unregister(sock)
    except KeyError:
        logger.warning(f"Tried to unregister unknown socket {sock.fileno()}")
    except Exception as e:
        logger.error(f"Error while unregistering socket {sock.fileno()}: {e}")

    if active_connections.pop(sock, None) is not None:
        logger.debug(f"Removed socket {sock.fileno()} from active connections")

    try:
        fd_being_closed = sock.fileno()
        sock.close()
        logger.info(f"Server closed connection on socket fd={fd_being_closed}")
    except Exception as e:
        logger.error(f"Error while closing socket {sock.fileno()}: {e}")

def handle_client_read(sock, mask):
    try:
        conn = active_connections[sock]
        if not conn:
            logger.warning(f"Connection object missing for socket fd={sock.fileno()}, closing connection")
            close_connection(sock)
            return

        data = sock.recv(4096)
        if not data:
            logger.info(f"Client closed connection (socket fd={sock.fileno()})")
            close_connection(sock)
            return

        conn['recv_buffer'] += data
        conn['last_active'] = time.time()

        if not is_full_http_request(conn['recv_buffer']):
            logger.debug(f"Partial request received, waiting for more data (socket fd={sock.fileno()})")
            return

        headers = parse_request(conn['recv_buffer'])
        method, path, version = headers[0].strip().split(' ')
        logger.info(f"Received request: {method} {path} {version} from '{conn.get('addr')[0]}'")

        conn_header = [h for h in headers if h.lower().startswith('connection:')]
        keep_alive = version == 'HTTP/1.1' and ('close' not in conn_header[0].lower() if conn_header else True)
        conn['keep_alive'] = keep_alive

        if method == 'GET' and path == '/':
            conn['send_buffer'] = serve_static_file(path)
        else:
            proxy_routes = get_config()['proxy']
            route = match_proxy_route(path, proxy_routes)
            if route:
                conn['send_buffer'] = proxy_to_upstream(sock, method, path, route)
                logger.info(f"Proxied request for {path} via upstream route (socket fd={sock.fileno()})")
            elif method == 'GET':
                conn['send_buffer'] = serve_static_file(path)
                logger.info(f"Served static file for {path} (socket fd={sock.fileno()})")
            else:
                response = b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n"
                conn['send_buffer'] = response
                logger.warning(f"Method not allowed: {method} (socket fd={sock.fileno()})")

        conn['stage'] = 'writing'
        conn['recv_buffer'] = b''  # Cleared after processing
        active_connections[sock] = conn
        selector.modify(sock, selectors.EVENT_WRITE, handle_client_write)

    except BlockingIOError:
        # Non-blocking socket temporarily unavailable, no error
        return 
    except Exception as e:
        logger.error(f"Error during read on socket fd={sock.fileno()}: {e}")
        close_connection(sock)

def handle_client_write(sock, mask):
    try:
        conn = active_connections[sock]
        if not conn or not conn['send_buffer']:
            logger.warning(f"No send buffer found or connection missing for socket fd={sock.fileno()}, closing")
            close_connection(sock)
            return

        sent = sock.send(conn['send_buffer'])
        conn['send_buffer'] = conn['send_buffer'][sent:]
        conn['last_active'] = time.time()

        if not conn['send_buffer']:  # Done sending
            logger.info(f"Finished sending response to '{conn.get('addr')[0]}'")
            if not conn['keep_alive']:
                logger.info(f"Closing connection (socket fd={sock.fileno()}) due to no keep-alive")
                close_connection(sock)
            else:
                conn['stage'] = 'reading'
                active_connections[sock] = conn
                selector.modify(sock, selectors.EVENT_READ, handle_client_read)

    except BlockingIOError:
        return # Socket not ready for writing, just return
    except Exception as e:
        logger.error(f"Error during write on socket fd={sock.fileno()}: {e}")
        close_connection(sock)

def handle_msg_receive(unix_sock, mask):
    client_fd = recv_fd_from_uds(unix_sock)
    if client_fd != -1:
        client_sock = socket.socket(fileno=client_fd)
        client_sock.setblocking(False)

        conn_state = {
            'recv_buffer': b'',
            'send_buffer': b'',
            'last_active': time.time(),
            'keep_alive': True,
            'stage': 'reading',
            'addr': client_sock.getpeername()
        }

        selector.register(client_sock, selectors.EVENT_READ, handle_client_read)
        active_connections[client_sock] = conn_state
        logger.debug(f"Received fd from master process: {client_fd}")

def run_worker(unix_sock):
    shutdown_flag = False
    logger.info(f"Worker PID {os.getpid()} started")

    def handle_sigterm(signum, frame):
        logger.info("Received SIGTERM signal")
        global shutdown_flag
        shutdown_flag = True

    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        selector.register(unix_sock, selectors.EVENT_READ, handle_msg_receive)
        logger.debug(f"Registered unix socket {unix_sock.fileno()} with selector")
    except Exception as e:
        logger.critical(f"Failed to register unix socket {unix_sock.fileno()} with selector: {e}")
        sys.exit(1)

    logger.info("Starting event loop")

    # Event Loop
    while not shutdown_flag:
        try:
            events = selector.select(timeout=5)
        except Exception as e:
            logger.error(f"Selector error: {e}")
            continue

        for key, mask in events:
            callback = key.data
            try:
                callback(key.fileobj, mask)
            except Exception as e:
                logger.error(f"Error in callback for fd {key.fd}: {e}")

        now = time.time()
        for sock, info in list(active_connections.items()):
            last_active = info.get('last_active', 0)
            if now - last_active > IDLE_TIMEOUT:
                logger.info(f"Closing idle connection: socket fd={sock.fileno()}")
                close_connection(sock)
    
    logger.debug("Shutdown initiated. Closing all active connections.")
    selector.close()
    
    for sock, info in list(active_connections.items()):
        close_connection(sock)

    logger.info(f"Finished cleaning up and now exiting..")
    sys.exit(0)
