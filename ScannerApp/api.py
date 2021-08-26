from time import sleep
from collections import deque
import json
from threading import Event

from .utils import isConnected
from .exceptions import AccessSpreadsheetError
from .logger import logger
from .barcode import BaseBarcodeScan

import gspread
from PyQt5.QtWidgets import qApp
from PyQt5.QtCore import (
    QObject,
    QThread,
    pyqtSignal,
    pyqtSlot,
    QTimer
)


DEFAULT_SLEEP_SECS = 300.0


class GSpreadWorker(QObject):
    """Worker object that checks a deque for items and passes them to the API."""

    def __init__(self, deque):
        super().__init__()

        self.deque = deque

        self.finished = pyqtSignal()

        self._stopIOthread = False
        self._itemFinished = False
        self._timerEvent = Event()

    def dequeChecker(self): 
        """Looping function that checks deque and pushes items to the handler."""
        while (True):
            if self.deque:
                item = self.deque.pop()
                self._itemFinished = False
                
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
                if not self._itemFinished:
                    self.deque.append(item)
                break

            sleep(0.005)

    def mainIOhandler(self, gs_function, *args, handler_wait_after=4.0, **kwargs):
        """Calls `gs_function` with provided arguments.
        Main gs_function for interacting with spreadsheet or other IO operations.
        Handles exceptions and API errors.
        Use `handler_wait_after` to define how long to sleep after successful finish."""
        API_error_count = 0
        while (True):
            if isConnected():
                try:
                    gs_function(*args, **kwargs)
                    # TODO need to test exception handling

                except AccessSpreadsheetError:
                    logger.error("API error count exceeded maximum tries.", 
                        exc_info=True)
                    self.kill()

                except gspread.exceptions.APIError:
                    if API_error_count >= 5:
                        logger.error("API error count exceeded maximum tries.", 
                            exc_info=True)
                        self.kill()
                        return
                    else:
                        API_error_count += 1
                   
                    logger.warning("API Error. Attempting retry.", exc_info=True)
                    self._wait(DEFAULT_SLEEP_SECS+60)

                except Exception:
                    logger.error('Unexpected error with mainIOhandler function', 
                        exc_info=True)
                    self.kill()

                else: 
                    self._itemFinished = True
                    self._wait(handler_wait_after) # to not max google api limits
                    return
                    
            else:
                logger.warning("Cannot reach internet. \n%s", 
                    f"Retrying connection in {DEFAULT_SLEEP_SECS/60} minutes.")
                self._wait(DEFAULT_SLEEP_SECS)

            if self._stopIOthread:
                break

    def _wait(self, time_secs: float):
        """Waits a number of seconds."""
        while not self._timerEvent.is_set():
            self._timerEvent.wait(time_secs)

        if self._stopIOthread:
            return

        self._timerEvent.clear()

    @pyqtSlot()
    def kill(self):
        self._stopIOthread = True
        self._timerEvent.set()

    @pyqtSlot()
    def run(self):
        self.dequeChecker()
        self.signals.finished.emit()


class GSpreadAPIHandler:

    def __init__(self, spreadsheet_key, sheet_name) -> None:
        
        self.spreadsheet_key = spreadsheet_key
        self.sheet_name = sheet_name

        self.deque = deque()
        self.addItem(dict(function=self.getAccessToSpreadsheet,
                          handler_wait_after=0))
        
        self.thread = QThread()
        self.worker = GSpreadWorker(self.deque)
        self.worker.finished.connect(self.shutdownApp)
        self.worker.moveToThread(self.thread)
        self.thread.start()

        self.refreshSpreadsheetTimer = QTimer()
        self.refreshSpreadsheetTimer.setInterval(10 * 60 * 1000) # every 10 minutes in msecs
        self.refreshSpreadsheetTimer.timeout.connect(self._refreshSpreadsheet)
        self.refreshSpreadsheetTimer.start()

    def addItem(self, item):
        """Parses item and adds it to the deque for use with GSpread."""
        #TODO add handling for incoming barcodes

        self.deque.appendleft(item)

    def kill(self):
        """Stops dequeworker thread. Once the thread closes the app shuts down."""
        self.worker.kill()

    def shutdownApp(self):
        """Shuts down main QApplication when connection to spreadsheet fails."""
        self.refreshSpreadsheetTimer.stop()
        qApp.quit()
    
    def getAccessToSpreadsheet(self):
        """Uses service account credentials to access the spreadsheet.
        Sets `self.ss` and `self.sheet` variables for operations."""
        try: 
            gc = gspread.service_account(filename='credentials.json')
            self.ss = gc.open_by_key(self.spreadsheet_key)
            self.sheet = self.ss.worksheet(self.sheet_name)
            return

        except (FileNotFoundError, json.decoder.JSONDecodeError):
            logger.error("Cannot access credentials and/or service account.", 
                exc_info=True)

        except TypeError:
            logger.error("Missing spreadsheet_key.", exc_info=True)

        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"Cannot find sheet named {self.sheet_name}.")
        
        raise AccessSpreadsheetError

    def _refreshSpreadsheet(self):
        self.addItem(self.getAccessToSpreadsheet)
