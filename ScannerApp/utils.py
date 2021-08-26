import socket
import json


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

class JSONEncoderWithFunctions(json.JSONEncoder):
    def default(self, o):
        if (callable(o)):
            return o.__name__
        else:
            return json.JSONEncoder.default(self, o)