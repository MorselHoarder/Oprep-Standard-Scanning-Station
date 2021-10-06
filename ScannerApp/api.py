from collections import deque
import json
from threading import Event

from ScannerApp.utils import isConnected
from ScannerApp.logger import logger

import gspread
from PyQt5.QtWidgets import qApp
from PyQt5.QtCore import QObject, QThread, pyqtSlot


DEFAULT_SLEEP_SECS = 300.0
MAX_API_TRIES = 5
REFRESH_TIMER_LENGTH_SECS = 600


class AccessSpreadsheetError(OSError):
    pass


class GSpreadFunctionNotFoundError(NameError):
    pass


class GSpreadWorker(QObject):
    """Worker object that checks a deque for items and passes them to the API.
    To be instantiated by a handler class that adds items to the deque for processing."""

    def __init__(self, deque, spreadsheet_key, sheet_name):
        super().__init__()

        self.deque = deque
        self.spreadsheet_key = spreadsheet_key
        self.sheet_name = sheet_name

        self._stopIOthread = False
        self._itemFinished = False
        self._timerEvent = Event()

        self.tryGSpreadCall(self.getAccessToSpreadsheet, handler_wait_after=0)

    def getAccessToSpreadsheet(self):
        """Uses service account credentials to access the spreadsheet.
        Sets `self.ss` and `self.sheet` variables for operations."""
        try:
            gc = gspread.service_account(filename="credentials.json")
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

    def getGSpreadFunction(self, func_name: str):
        """Takes func_name string and returns GSpread method of same name.
        If func_name is not found, raises GSpreadFunctionNotFoundError."""
        if func_name == "insert_rows":
            return self.sheet.insert_rows
        elif func_name == "delete_rows":
            return self.sheet.delete_rows
        elif func_name == "getAccessToSpreadsheet":
            return self.getAccessToSpreadsheet
        else:
            raise GSpreadFunctionNotFoundError("GSpread function name not found.")

    def parseDequeItem(self, item: dict):
        """Parses `item` for GSpread function name and replaces it with a function reference.
        `item` should have key named `function` with a string value containing a GSpread function name."""
        func_ref = self.getGSpreadFunction(str(item["function"]))
        item["function"] = func_ref
        return item

    def dequeChecker(self):
        """Looping function that checks deque and pushes items to the handler."""
        while True:
            if self.deque:
                raw_item = self.deque.pop()
                self._itemFinished = False

                try:
                    item = self.parseDequeItem(raw_item)
                    self.tryGSpreadCall(**item)

                except TypeError:
                    logger.warning(
                        "Item of wrong type added to queue: %s of type %s",
                        str(item),
                        type(item),
                    )
                    self._itemFinished = True

                except KeyError:
                    logger.warning(f'"function" key not found in deque item: {item}')
                    self._itemFinished = True

                except GSpreadFunctionNotFoundError:
                    logger.warning(
                        f"GSpread Function reference not found for item: {item}"
                    )
                    self._itemFinished = True

            if self._stopIOthread:
                if not self._itemFinished:
                    self.deque.append(raw_item)
                break

            self._wait(0.005)

    def tryGSpreadCall(self, function, *args, handler_wait_after=4.0, **kwargs):
        """Calls `function` with *args, **kwargs.
        Main method for interacting with spreadsheet or other IO operations.
        Handles exceptions and API errors.
        Use `handler_wait_after` to define how long to sleep after successful finish."""
        API_error_count = 0
        while True:
            if isConnected():
                try:
                    function(*args, **kwargs)
                    # TODO need to test exception handling

                except AccessSpreadsheetError:
                    logger.error(
                        "Unexpected error when accessing spreadsheet.", exc_info=True
                    )
                    self.kill()

                except gspread.exceptions.APIError:
                    if API_error_count >= MAX_API_TRIES:
                        logger.error(
                            "API error count exceeded maximum tries.", exc_info=True
                        )
                        self.kill()
                        return
                    else:
                        API_error_count += 1

                    logger.warning("API Error. Attempting retry.", exc_info=True)
                    self._wait(DEFAULT_SLEEP_SECS + 60)

                except Exception:
                    logger.error(
                        "Unexpected error with tryGSpreadCall function.", exc_info=True
                    )
                    self.kill()

                else:
                    self._itemFinished = True
                    self._wait(handler_wait_after)  # to not max google api limits
                    return

            else:
                logger.warning(
                    "Cannot reach internet. \n%s",
                    f"Retrying connection in {DEFAULT_SLEEP_SECS/60} minutes.",
                )
                self._wait(DEFAULT_SLEEP_SECS)

            if self._stopIOthread:
                break

    def _wait(self, time_secs: float):
        """Waits a number of seconds."""
        self._timerEvent.wait(time_secs)

    @pyqtSlot()
    def kill(self):
        self._stopIOthread = True
        self._timerEvent.set()

    @pyqtSlot()
    def run(self):
        print("thread started")
        self.dequeChecker()


class GSpreadAPIHandler:
    """Generates thread to interface with GSpread."""

    def __init__(self, spreadsheet_key, sheet_name) -> None:

        self.deque = deque()

        self.thread = QThread()
        self.worker = GSpreadWorker(self.deque, spreadsheet_key, sheet_name)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.shutdownApp)
        self.thread.start()

    def addItem(self, item: dict):
        """Adds an item to the deque for the worker thread to parse."""
        self.deque.appendleft(item)

    def kill(self):
        """Stops dequeworker thread. Once the thread closes the app shuts down."""
        self.worker.kill()

    def shutdownApp(self):
        """Shuts down main QApplication. Used when critical or unexpected error occurs
        and app needs to restart."""
        qApp.quit()
