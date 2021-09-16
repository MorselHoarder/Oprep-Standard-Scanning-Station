from threading import Event

_timerEvent = Event()

def _wait(time_secs: float):
    """Waits a number of seconds."""
    _timerEvent.wait(time_secs)

    # _timerEvent.clear()

_wait(1.0)
print("waited 1 second")
print(_timerEvent.is_set())