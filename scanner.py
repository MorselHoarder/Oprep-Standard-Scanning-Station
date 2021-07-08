"""
Orep Standard Scanning Station by Andrew Schult

Had much help from the ZetCode PyQt5 tutorial
Website: zetcode.com
"""

# stdlib
import sys
import re
from time import sleep
import datetime as dt
import configparser
import queue
import traceback
import socket
import json
import logging
from random import randint

# dependencies
import gspread
from PyQt5.QtCore import (
    Qt, 
    QObject,
    QProcess,
    QTimer,
    QRunnable,
    QThreadPool,
    pyqtSignal,
    pyqtSlot
)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QWidget,
    QApplication, 
    QLineEdit, 
    QLabel, 
    QGridLayout,
    QMessageBox, 
    qApp
)


log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=log_format, 
                    handlers=[logging.FileHandler('errors.log')],
                    level=logging.INFO)
logger = logging.getLogger(__name__)


SCRIPT_VERSION = "1.0.0"
QUEUE_DUMP_FILE = "queue_dump.json"
QUEUE_ITEMS_KEY = "queue_items"


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


class AccessSpreadsheetError(OSError):
    pass


class JSONEncoderWithFunctions(json.JSONEncoder):
    def default(self, o):
        if (callable(o)):
            return o.__name__
        else:
            return json.JSONEncoder.default(self, o)

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


class BarcodeDisplay(QWidget):

    def __init__(self, regex_pattern, spreadsheet_key, destination_sheet):
        super().__init__()
        self.regex_pattern = regex_pattern
        self.spreadsheet_key = spreadsheet_key
        self.destination_sheet = destination_sheet

        qApp.aboutToQuit.connect(self._cleanupRoutine)
        
        self.initUI()

    def initUI(self):

        self.setGeometry(50, 50, 720, 480)
        self.setWindowTitle('Oprep Standard Scanning Station')
        self.setWindowIcon(QIcon('logo.png'))
        with open("stylesheet.qss", "r") as stylesheet:
            self.setStyleSheet(stylesheet.read())

        self.grid = QGridLayout(self)
        self.setLayout(self.grid)

        self.le = QLineEdit(self)
        self.le.setProperty('class', 'inputField')

        self.display = QLabel("No Barcode Yet")
        self.display.setProperty('class', 'display')

        self.alert = QLabel("")
        self.alert.setProperty('class', 'alert')
        self.alert.setWordWrap(True)
        self.alert.setAlignment(Qt.AlignCenter)

        l1 = QLabel("Scan here:")
        l1.setProperty('class', 'headers')
        l2 = QLabel("Previous scan: ")
        l2.setProperty('class', 'headers')

        self.grid.addWidget(l1, 0, 0)
        self.grid.addWidget(l2, 1, 0)
        self.grid.addWidget(self.le, 0, 1)
        self.grid.addWidget(self.display, 1, 1)
        self.grid.addWidget(self.alert, 0, 2, 2, 1)

        # initialize empty list to hold barcodes
        # UI only displays 10 rows, but keep 20 in case we rotate up
        self.entries = [['' for y in range(3)] for x in range(20)]
        self.updateList()

        # TODO change this queue to a deque for appending functionality
        self.queue = queue.Queue()
        self.threadpool = QThreadPool()

        self.IOthreadWorker = QueueWorker(self.queue)
        self.IOthreadWorker.signals.finished.connect(self.close)
        self.threadpool.start(self.IOthreadWorker)

        # get initial access to spreadsheet
        self.queue.put(dict(function=self.getAccessToSpreadsheet))

        # TODO get this to read properly, needs self.sheet populated. 
        # self.readQueueFromJSON()

        self._refresh_spreadsheet_timer = QTimer()
        self._refresh_spreadsheet_timer.setInterval(10 * 60 * 1000) # every 10 minutes in msecs
        self._refresh_spreadsheet_timer.timeout.connect(self._refreshSpreadsheet)
        self._refresh_spreadsheet_timer.start()

        self.compiled_pattern = re.compile(self.regex_pattern, flags=re.IGNORECASE)

        # self.show()
        self.showMaximized() # displays the window at full res

    def getAccessToSpreadsheet(self):
        """Uses service account credentials to access the spreadsheet.
        Sets `self.ss` and `self.sheet` variables for operations."""
        try: 
            gc = gspread.service_account(filename='credentials.json')
            self.ss = gc.open_by_key(self.spreadsheet_key)
            self.sheet = self.ss.worksheet(self.destination_sheet)
            return

        except (FileNotFoundError, json.decoder.JSONDecodeError):
            self.alert.setText("SERVICE ACCOUNT FAILURE")
            logger.error("Cannot access credentials and/or service account.", 
                exc_info=True)

        except TypeError:
            self.alert.setText("SPREADSHEET CONNECTION FAILURE")
            logger.error("Missing spreadsheet_key.", exc_info=True)

        except gspread.exceptions.WorksheetNotFound:
            self.alert.setText(f"WORKSHEET {self.destination_sheet} NOT FOUND")
            logger.error(f"Cannot find sheet named {self.destination_sheet}.")
        
        raise AccessSpreadsheetError

    def _refreshSpreadsheet(self):
        """To be called by `_refresh_spreadsheet_timer`.
        Puts `getAccessToSpreadsheet` into queue."""
        self.queue.put(dict(function=self.getAccessToSpreadsheet))

    def updateList(self): 
        # updates the list UI
        # first make a list of (x,y) positions in the widget grid
        # skip top two rows which hold widgets we don't want rotated
        positions = [(i, j) for i in range(2, 12) for j in range(3)] 

        # flatten the entries list
        entries = [a for b in self.entries for a in b]  

        for position, entry in zip(positions, entries):
            label = QLabel(entry)
            label.setProperty('class', 'entry')
            # put the new widget at the (x,y) position
            self.grid.addWidget(label, *position)

    def keyPressEvent(self, e):  
        # where the fun begins
        # QT function that waits for an 'enter' keystroke
        if (e.key() == Qt.Key_Return) and (len(self.le.text()) > 0):
            input_str = self.le.text()
            self.le.clear()
            self.display.setText('"'+input_str+'"')
            self.handleInput(input_str)

    def handleInput(self, input_str):
        if input_str == "remove last barcode":
            if self.entries[0][0] != "Invalid Barcode!":
                self.queue.put(dict(function=self.sheet.delete_rows, start_index=1))
            self.rotateListUp()
        elif input_str == "retry connection":
            self.queue.put(self.getAccessToSpreadsheet)
        else:
            mat, exp_date = self.regexMatchBarcode(input_str)
            if mat != "Invalid Barcode!":
                self.queue.put(dict(function=self.sheet.insert_row, values=[input_str]))
            new_row = self.composeNewRow(mat, exp_date)
            self.rotateListDown(new_row)

    def rotateListDown(self, new_row):
        self.entries = new_row + self.entries
        del self.entries[-1]
        self.clearLayout()
        self.updateList()

    def rotateListUp(self):
        del self.entries[0]
        self.clearLayout()
        self.updateList()

    def regexMatchBarcode(self, barcode):
        m = self.compiled_pattern.fullmatch(barcode)
        if m:
            mat = m.group(1)
            exp_date = self.formatDateGroup(m.group(2))
        else:
            mat = "Invalid Barcode!"
            exp_date = "This barcode is not from a prepped standard."
        return mat, exp_date

    def composeNewRow(self, id_std, exp_date):
        if id_std == "Invalid Barcode!":
            new_row = [[id_std, exp_date, "Scanned: " + self.getTimeStamp()]]
        else:
            new_row = [[id_std, "Expires: " + exp_date,
                        "Scanned: " + self.getTimeStamp()]]
        return new_row

    @staticmethod
    def formatDateGroup(date_str):
        if (len(date_str) == 5):  # to account for early bug where date was 5 digits
            ls = list(date_str)
            ls.insert(2, "0")
            date_str = "".join(ls)
        d = dt.datetime.strptime(date_str, "%m%d%y")
        return d.strftime('%m/%d/%Y')

    @staticmethod
    def getTimeStamp():
        ts = dt.datetime.now()
        ts = ts.strftime('%m/%d/%y %H:%M')
        return ts

    def clearLayout(self):  # thank mr. riverbank
        WIDGET_TOTAL = 30   # num of widgets that need deleting
        TOP_ROW = 5         # num of widgets in front to keep
        i = 0
        while i < WIDGET_TOTAL:
            i += 1
            item = self.grid.takeAt(TOP_ROW)
            if not item:
                continue
            w = item.widget()
            if w:
                w.deleteLater()

    def combineQueueItem(self, function, *args, **kwargs):
        if args:
            return list(function, *args)
        else:
            return dict(kwargs, function=function)

    def readQueueFromJSON(self):
        "Gets any queue items from queue_dump.json and puts them into the queue."
        try: 
            with open(QUEUE_DUMP_FILE) as queue_dump:
                data_dict = json.load(queue_dump)
        except FileNotFoundError:
            logger.info("No queue_dump.json file found.")
            return
        
        for item in data_dict[QUEUE_ITEMS_KEY]:
            if isinstance(item, dict):
                func_name = item.get('function')
                if func_name == 'insert_row':
                    self.queue.put(dict(function=self.sheet.insert_row, 
                                        values=item.get('values')))
                elif func_name == 'delete_rows':
                    self.queue.put(dict(function=self.sheet.delete_rows, 
                                        start_index=item.get('start_index')))
        
        # clear old values
        data_dict[QUEUE_ITEMS_KEY] = ''
        with open(QUEUE_DUMP_FILE, "w") as queue_dump:
            json.dump(data_dict, queue_dump, indent=2)

    def dumpQueueToJSON(self, current_item=None):
        "Puts every item left in the queue into json file"
        data_dict = dict(version=SCRIPT_VERSION)

        item_list = []
        if current_item is not None:
            item_list.append(current_item)

        while (True):
            try:
                item = self.queue.get(block=False)
            except queue.Empty:
                break 
            else:
                item_list.append(item)

        data_dict[QUEUE_ITEMS_KEY] = item_list
        
        with open(QUEUE_DUMP_FILE, "w") as queue_dump:
            json.dump(data_dict, queue_dump, indent=2, cls=JSONEncoderWithFunctions)

        logger.info("Queue dumped to JSON")

    def msgbox(self, label_text=None, window_title="Alert", timer_length_secs=5):
        """Creates a simple message dialog with cancel button that counts down.
        If cancel or escape is pressed, returns False. Otherwise timeout returns True.
        Leave `label_text` as `None` to use default text."""
        # TODO get this to spawn on main thread
        mb = QMessageBox()
        mb.setIcon(QMessageBox.Warning)

        if label_text is None:
            mb.setText("Scanning system has encountered an error and needs to close."
                       "\nPreviously scanned barcodes will be remembered upon restart."
                       "\nDO NOT RESCAN OLD BARCODES.")
        else:
            mb.setText(label_text)

        mb.setWindowTitle(window_title)
        mb.setStandardButtons(QMessageBox.Cancel)
        mb.setEscapeButton(QMessageBox.Cancel)
        mb.buttonClicked.connect(mb.reject)
        timer = QTimer.singleShot(timer_length_secs*1000, mb.accept)

        # TODO cancel doesn't work still. Maybe take it out?
        if mb.exec() == 1:
            return True
        else:
            return False

    def _stopAllThreads(self):
        self.IOthreadWorker.kill()
        self._refresh_spreadsheet_timer.stop()
        self.threadpool.waitForDone(msecs=100)

    def closeEvent(self, event) -> None:
        print("close event emitted")

        # TODO add handling for _current_item and _msg_warning
        if not self.msgbox(): # cancel pressed
            return

        return event.accept()

    def _cleanupRoutine(self) -> None:
        self._stopAllThreads()
        self.dumpQueueToJSON()




def main():
    # pattern ignores case by default
    BARCODE_PATTERN = r"^(pp[0-9]{4,5}|eph[0-9]{4}|[0-9]{4,5})[A-Za-z]{0,2}-([0-9]{5,6}),"
    # SPREADSHEET_KEY = "1c0J8E4Z96jPnu2hqgwEEXzWmhldv-BHCU66rwUCrWw0"
    SPREADSHEET_KEY = "11Y3oufYpwWanKRB0KzxsrhkqErfPgak-LylKCt6a4i0" # test spreadsheet
    SHEET_NAME_TO_SCAN = "Scan"

    app = QApplication(sys.argv)
    _ = BarcodeDisplay(BARCODE_PATTERN, SPREADSHEET_KEY, SHEET_NAME_TO_SCAN)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
