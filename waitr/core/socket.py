import array 
import socket

def send_fd_via_uds(sock: socket.socket, fd: int) -> None:
    """
    Send a file descriptor over a Unix domain socket.

    Parameters:
        sock (socket.socket): A Unix domain socket object used to send the file descriptor.
        fd (int): The file descriptor to send.

    This function uses the SCM_RIGHTS control message to pass the given file descriptor
    to another process over the provided Unix domain socket.
    """
    fds = array.array("i", [fd])
    sock.sendmsg([b"FD"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, fds)])

def recv_fd_from_uds(sock: socket.socket) -> int:
    """
    Receive a file descriptor over a Unix domain socket.

    Parameters:
        sock (socket.socket): A Unix domain socket object through which the file descriptor is arriving.

    If no file descriptor is present in the message, -1 is returned.
    """
    msg, ancdata, *_ = sock.recvmsg(1, socket.CMSG_LEN(4))
    for cmsg_level, cmsg_type, cmsg_data in ancdata:
        if cmsg_level == socket.SOL_SOCKET and cmsg_type == socket.SCM_RIGHTS:
            fds = array.array("i")
            fds.frombytes(cmsg_data[:4])
            client_fd = fds[0]
            return client_fd
    return -1