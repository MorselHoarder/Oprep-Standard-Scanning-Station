from collections import deque
import json
import os
from threading import Event

from ScannerApp.utils import isConnected
from ScannerApp.logger import logger

import gspread
from PyQt5.QtWidgets import qApp
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

API_VERSION = "1.0.0"
DEQUE_ITEMS_KEY = "Items"
DEQUE_DUMP_FILE = "deque_dump.json"

DEFAULT_SLEEP_SECS = 300.0
MAX_API_TRIES = 5
REFRESH_TIMER_LENGTH_SECS = 600


class AccessSpreadsheetError(OSError):
    pass


class GSpreadFunctionNotFoundError(NameError):
    pass


class JSONEncoderWithFunctions(json.JSONEncoder):
    def default(self, o):
        if callable(o):
            return o.__name__
        else:
            return json.JSONEncoder.default(self, o)


class WorkerSignals(QObject):
    """Worker signals"""

    finished = pyqtSignal()


class GSpreadWorker(QObject):
    """Worker object that checks a deque for items and passes them to the API.
    To be instantiated by a handler class that adds items to the deque for processing."""

    def __init__(self, deque, spreadsheet_key, sheet_name):
        super().__init__()

        self.signals = WorkerSignals()

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
            logger.info("Spreadsheet access successful.")
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
        elif func_name == "delete_row":
            return self.sheet.delete_row
        elif func_name == "getAccessToSpreadsheet":
            return self.getAccessToSpreadsheet
        elif func_name == "test":
            return self.test
        else:
            raise GSpreadFunctionNotFoundError("GSpread function name not found.")

    def parseDequeItem(self, item: dict):
        """Parses `item` for GSpread function name and replaces it with a function reference.
        `item` should have key named `function` with a string value containing a GSpread function name."""
        func_ref = self.getGSpreadFunction(str(item["function"]))
        item_copy = item.copy()
        item_copy["function"] = func_ref
        return item_copy

    def dequeChecker(self):
        """Looping function that checks deque and pushes items to the handler."""
        raw_item = None
        while True:
            if self.deque:
                raw_item = self.deque.pop()
                self._itemFinished = False

                try:
                    if raw_item is not None:
                        item = self.parseDequeItem(raw_item)
                        self.tryGSpreadCall(**item)

                except TypeError:
                    logger.warning(
                        "Item of wrong type added to queue: %s of type %s",
                        str(raw_item),
                        type(raw_item),
                    )
                    self._itemFinished = True

                except KeyError:
                    logger.warning(
                        f'"function" key not found in deque item: {raw_item}'
                    )
                    self._itemFinished = True

                except GSpreadFunctionNotFoundError:
                    logger.warning(
                        f"GSpread Function reference not found for item: {raw_item}"
                    )
                    self._itemFinished = True

            if self._stopIOthread:
                if not self._itemFinished and raw_item is not None:
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
        self.dequeChecker()
        logger.info("GSpreadWorker finished.")
        self.signals.finished.emit()


class GSpreadAPIHandler(QObject):
    """Generates thread to interface with GSpread."""

    def __init__(self, spreadsheet_key, sheet_name) -> None:
        super().__init__()
        self.spreadsheet_key = spreadsheet_key
        self.sheet_name = sheet_name

        self.deque = deque()

        self.isShutDown = False
        self._spawnThread()

        self._readDequeFromJSON()

    def addItem(self, item: dict):
        """Adds an item to the deque for the worker thread to parse."""
        self.deque.appendleft(item)

    def shutdown(self):
        """Shuts down API connection thread and saves unsent deque items."""
        logger.info("Shutting down API connection.")
        self._killThread()
        self._dumpDequeToJSON()

    def _spawnThread(self):
        """Subroutine that handles starting a thread with GSpreadWorker"""
        self.thread = QThread()
        self.worker = GSpreadWorker(self.deque, self.spreadsheet_key, self.sheet_name)
        self.worker.signals.finished.connect(self.thread.quit)
        self.worker.signals.finished.connect(self.worker.deleteLater)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._restartThread)
        self.thread.start()

    def _restartThread(self):
        if not self.isShutDown:
            logger.info("Restarting API connection.")
            self._spawnThread()

    def _killThread(self):
        """Stops dequeworker thread."""
        logger.info("Killing GSpreadAPIHandler thread.")
        self.isShutDown = True
        self.worker.kill()
        if self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def _dumpDequeToJSON(self):
        """Dumps all remaining items in the deque to JSON file"""
        data_dict = dict(version=API_VERSION)

        item_list = []

        while True:
            try:
                item = self.deque.pop()
            except IndexError:
                break
            else:
                item_list.append(item)

        data_dict[DEQUE_ITEMS_KEY] = item_list

        try:
            with open(DEQUE_DUMP_FILE, "w+") as deque_dump:
                json.dump(data_dict, deque_dump, indent=2, cls=JSONEncoderWithFunctions)
        except FileNotFoundError:
            logger.info("No deque_dump.json file found.")
        except PermissionError:
            logger.info("No write permissions for deque_dump.json file.")
        else:
            logger.info("Deque dumped to JSON.")

    def _readDequeFromJSON(self):
        "Gets any deque items from deque_dump.json and puts them into the deque."
        try:
            if os.path.exists(DEQUE_DUMP_FILE):
                with open(DEQUE_DUMP_FILE, "r") as deque_dump:
                    data_dict = json.load(deque_dump)
                    for item in data_dict[DEQUE_ITEMS_KEY]:
                        self.addItem(item)
                with open(DEQUE_DUMP_FILE, "w+") as deque_dump:
                    data_dict[DEQUE_ITEMS_KEY] = []  # clear old values
                    json.dump(data_dict, deque_dump, indent=2)
                logger.info("Read items from deque_dump.json into deque.")
            else:
                logger.info("No deque_dump.json file found.")
        except PermissionError:
            logger.info("No read/write permissions for deque_dump.json file.")
        except json.decoder.JSONDecodeError:
            logger.warning(
                "deque_dump.json corrupted. File will be removed.", exc_info=True
            )
            os.remove(DEQUE_DUMP_FILE)
