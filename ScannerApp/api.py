from time import sleep
from random import randint

from .utils import isConnected
from .exceptions import AccessSpreadsheetError
from .logger import logger

import gspread
from PyQt5.QtCore import (
    QObject,
    QRunnable,
    pyqtSignal,
    pyqtSlot
)


class WorkerSignals(QObject):
    """This class holds the signals for QRunnable child classes
    in order for them to be able to emit signals."""
    finished = pyqtSignal()


class QueueWorker(QRunnable):

    def __init__(self, queue):
        super().__init__()

        self.queue = queue

        self.signals = WorkerSignals()

        self._stopIOthread = False

    def queueChecker(self): 
        """Looping function that checks queue and pushes items to the handler."""
        while (True):
            if (self.queue.qsize() > 0):
                item = self.queue.get()
                if callable(item):
                    self.mainIOhandler(item)
                elif isinstance(item, dict):
                    self.mainIOhandler(**item)
                elif isinstance(item, (tuple, list)):
                    self.mainIOhandler(*item)
                else:
                    logger.warning('Item of wrong type added to queue: %s of type %s', 
                        str(item), type(item))

            if self._stopIOthread:
                break

            sleep(0.005) #free CPU briefly

    def mainIOhandler(self, function, *args, handler_wait_after=4, **kwargs):
        """Calls `function` with provided arguments.
        Main function for interacting with spreadsheet or other IO operations.
        Handles exceptions and API errors.
        Use `handler_wait_after` to define how long to sleep after successful finish."""
        API_error_count = 0
        while (True):
            if isConnected():
                try:
                    function(*args, **kwargs)
                    # TODO need to test exception handling

                except AccessSpreadsheetError as e:
                    w = ("AccessSpreadsheetError raised. See errors.log for details."
                        "\nRestarting app in 10 seconds.")
                    self.shutdownWorker(msg_warning=w)

                except gspread.exceptions.APIError as e:
                    if API_error_count >= 5:
                        # TODO add serious error handling
                        logger.warning("API error count exceeded maximum tries.", exc_info=True)
                        self.shutdownWorker(self.combineQueueItem(function, *args, **kwargs))
                    else:
                        API_error_count += 1

                    code = e.response.json()['error']['code']
                    message = e.response.json()['error']['message']

                    random_int = randint(1, 120)

                    if (code == 429):                      
                        logger.warning("API rate limit exceeded. %s", 
                            f"Retrying in {5*API_error_count+(random_int/60):.2f} minutes.")
                        sleep(300*API_error_count+random_int)
                    else:
                        logger.error(f"API Error {str(code)}: {str(message)}. \n%s %s \n%s", 
                            "The following command was not executed:",
                            f"'{function.__name__}' with arguments: {args} {kwargs}",
                            f"Retrying command in {10+(random_int/60):.2f} minutes.",
                            exc_info=True)
                        sleep(600+random_int)

                except Exception:
                    logger.error('Unexpected error with mainIOhandler function', 
                        exc_info=True)
                    self.shutdownWorker(self.combineQueueItem(function, *args, **kwargs))

                else: 
                    sleep(handler_wait_after) # to not max google api limits
                    return
                    
            else:
                random_int = randint(1, 120)
                logger.warning("Cannot reach internet. \n%s %s \n%s", 
                            "The following command was not executed:",
                            f"'{function.__name__}' with arguments: {args} {kwargs}",
                            f"Retrying connection in {10+(random_int/60):.2f} minutes.")
                sleep(600+random_int)

            if self._stopIOthread:
                break

    def shutdownWorker(self, current_queue_item=None):
        self.kill()
        # TODO add handling for current item with error

    @pyqtSlot()
    def kill(self):
        self._stopIOthread = True

    @pyqtSlot()
    def run(self):
        self.queueChecker()
        self.signals.finished.emit()