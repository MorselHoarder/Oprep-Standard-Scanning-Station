from time import sleep
from collections import deque
import json
from threading import Event

from ScannerApp.utils import isConnected
from ScannerApp.exceptions import AccessSpreadsheetError
from ScannerApp.logger import logger

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
MAX_API_TRIES = 5
REFRESH_TIMER_LENGTH_SECS = 600


class GSpreadWorker(QObject):
    """Worker object that checks a deque for items and passes them to the API."""

    def __init__(self, deque):
        super().__init__()

        self.deque = deque

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
                    self._itemFinished = True

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
                    logger.error("Unexpected error when accessing spreadsheet.", 
                        exc_info=True)
                    self.kill()

                except gspread.exceptions.APIError:
                    if API_error_count >= MAX_API_TRIES:
                        logger.error("API error count exceeded maximum tries.", 
                            exc_info=True)
                        self.kill()
                        return
                    else:
                        API_error_count += 1
                   
                    logger.warning("API Error. Attempting retry.", exc_info=True)
                    self._wait(DEFAULT_SLEEP_SECS+60)

                except Exception:
                    logger.error('Unexpected error with mainIOhandler function.', 
                        exc_info=True)
                    self.kill()

                else: 
                    print("api call finished:", str(gs_function))
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
        print("thread started")
        self.dequeChecker()


class GSpreadAPIHandler:

    def __init__(self, spreadsheet_key, sheet_name) -> None:
        
        self.spreadsheet_key = spreadsheet_key
        self.sheet_name = sheet_name

        self.deque = deque()
        self.addItem("getAccessToSpreadsheet")
        
        self.thread = QThread()
        self.worker = GSpreadWorker(self.deque)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.shutdownApp)
        self.thread.start()

        self.refreshSpreadsheetTimer = QTimer()
        self.refreshSpreadsheetTimer.setInterval(REFRESH_TIMER_LENGTH_SECS * 1000)
        self.refreshSpreadsheetTimer.timeout.connect(self._refreshSpreadsheet)
        self.refreshSpreadsheetTimer.start()

    def addItem(self, item):
        """Parses item and adds it to the deque for use with GSpread.
        item should be a dictionary, list, or string. 
        If a string, it should be a GSpread function name.
        Dict should have key named `function` with a string value containing a GSpread function name. 
        First object in list should be a string that matches a GSpread function name. 
        Entire item will be passed to the api after function reference is added."""
        if isinstance(item, str):
            func_ref = self.getGspreadFunction(item)
            if func_ref is not None:
                item = func_ref

        elif isinstance(item, dict):
            func_ref = self.getGspreadFunction(str(item.get('function')))
            if func_ref is not None:
                item['function'] = func_ref
            
        elif isinstance(item, list):
            func_ref = self.getGspreadFunction(str(item.pop(0)))
            if func_ref is not None:
                item.insert(0, func_ref)

        else:
            logger.info('Item of wrong type added to api: %s of type %s', 
                str(item), type(item))
            return

        if func_ref is None:
            logger.warning('Function reference not found for item: %s', str(item))
            return

        self.deque.appendleft(item)
        print("appendleft successful:", item)

    def getGspreadFunction(self, func_name: str):
        """Takes func_name string and returns GSpread method of same name.
        If func_name is not found, return None."""
        if func_name == "insert_rows":
            return self.sheet.insert_rows
        elif func_name == "delete_rows":
            return self.sheet.delete_rows
        elif func_name == "getAccessToSpreadsheet":
            return self.getAccessToSpreadsheet
        else:
            return None

    def kill(self):
        """Stops dequeworker thread. Once the thread closes the app shuts down."""
        self.worker.kill()

    def shutdownApp(self):
        """Shuts down main QApplication. Used when critical or unexpected error occurs
        and app needs to restart."""
        self.refreshSpreadsheetTimer.stop()
        qApp.quit()
    
    def getAccessToSpreadsheet(self):
        """Uses service account credentials to access the spreadsheet.
        Sets `self.ss` and `self.sheet` variables for operations."""
        try: 
            gc = gspread.service_account(filename='credentials.json')
            self.ss = gc.open_by_key(self.spreadsheet_key)
            self.sheet = self.ss.worksheet(self.sheet_name)
            print("spreadsheet access successful")
            return

        except (FileNotFoundError, json.decoder.JSONDecodeError):
            err_str = "Cannot access credentials and/or service account."

        except TypeError:
            err_str = "Missing spreadsheet_key."

        except gspread.exceptions.WorksheetNotFound:
            err_str = f"Cannot find sheet named {self.sheet_name}."
        
        raise AccessSpreadsheetError(err_str)

    def _refreshSpreadsheet(self):
        self.addItem("getAccessToSpreadsheet")
