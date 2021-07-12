import datetime as dt
import socket
import json


def formatDateGroup(date_str: str) -> str:
    if (len(date_str) == 5):  # to account for early bug where date was 5 digits
        ls = list(date_str)
        ls.insert(2, "0")
        date_str = "".join(ls)
    d = dt.datetime.strptime(date_str, "%m%d%y")
    return d.strftime('%m/%d/%Y')

def getTimeStamp(dt: dt.datetime) -> str:
    return dt.strftime('%m/%d/%y %H:%M')

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