import socket


def isConnected():
    """Detects an internet connection."""
    try:
        conn = socket.create_connection(("1.1.1.1", 80))
        if conn is not None:
            conn.close
        return True
    except OSError:
        pass
    return False
