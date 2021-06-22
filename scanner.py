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
import threading
import socket
import json
import logging
from random import randint

# dependencies
import gspread
from PyQt5.QtCore import (
    Qt, 
    QProcess,
    QTimer
)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QWidget,
    QApplication, 
    QLineEdit, 
    QLabel, 
    QGridLayout, 
    qApp
)


log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=log_format, 
                    handlers=[logging.FileHandler('errors.log')],
                    level=logging.INFO)
logger = logging.getLogger(__name__)


class AccessSpreadsheetError(OSError):
    pass


class BarcodeDisplay(QWidget):

    def __init__(self, regex_pattern, spreadsheet_key, destination_sheet):
        super().__init__()
        self.regex_pattern = regex_pattern
        self.spreadsheet_key = spreadsheet_key
        self.destination_sheet = destination_sheet
        
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

        self.queue = queue.Queue()
        self.stopIOthread = False
        self.IOthread = threading.Thread(target=self.queueChecker, daemon=True).start()

        # get initial access to spreadsheet
        self.queue.put(dict(function=self.getAccessToSpreadsheet, handler_wait_after=0))

        self._refresh_spreadsheet_timer = QTimer()
        self._refresh_spreadsheet_timer.setInterval(60 * 60 * 1000) # every 1 hour in msecs
        self._refresh_spreadsheet_timer.timeout.connect(self._refreshSpreadsheet)
        self._refresh_spreadsheet_timer.start()

        self.compiled_pattern = re.compile(self.regex_pattern, flags=re.IGNORECASE)

        # self.show()
        self.showMaximized() # displays the window at full res

    @staticmethod
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

    def getAccessToSpreadsheet(self):
        """Uses service account credentials to access the spreadsheet.
        Sets `self.ss` and `self.sheet` variables for operations."""
        if self.isConnected():
            try: 
                gc = gspread.service_account(filename='credentials.json')
            except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
                self.alert.setText("SERVICE ACCOUNT FAILURE")
                logger.error("Cannot access credentials and/or service account.", 
                    exc_info=True)
                raise AccessSpreadsheetError from e
            else:
                try:
                    self.ss = gc.open_by_key(self.spreadsheet_key)
                except TypeError as e:
                    self.alert.setText("SPREADSHEET CONNECTION FAILURE")
                    logger.error("Missing spreadsheet_key.", exc_info=True)
                    raise AccessSpreadsheetError from e
                else:
                    try:
                        if self.destination_sheet is not None:
                            self.sheet = self.ss.worksheet(self.destination_sheet)
                        else:
                            self.sheet = self.ss.sheet1
                        print("Spreadsheet access successful")
                    except gspread.exceptions.WorksheetNotFound as e:
                        self.alert.setText(f"WORKSHEET {self.destination_sheet} NOT FOUND")
                        logger.error(f"Cannot find sheet named {self.destination_sheet}.")
                        raise AccessSpreadsheetError from e

    def mainIOhandler(self, function, *args, handler_wait_after=4, **kwargs):
        """Calls `function` with provided arguments.
        Main function for interacting with spreadsheet or other IO operations.
        Handles exceptions and API errors.
        Use `handler_wait_after` to define how long to sleep after successful finish."""
        API_error_count = 0
        while (True):
            if self.isConnected() is True:
                try:
                    function(*args, **kwargs)
                except AccessSpreadsheetError as e:
                    print("AccessSpreadsheetError")
                    #TODO add handling / make dialog box for serious alerts
                    self.restartApp()
                except gspread.exceptions.APIError as e:
                    if API_error_count >= 5:
                        # TODO add serious error handling
                        logger.warning("API error count exceeded maximum tries.", exc_info=True)
                        self.restartApp()
                    else:
                        API_error_count += 1
                    code = e.response.json()['error']['code']
                    message = e.response.json()['error']['message']
                    self.alert.setText(f"{str(code)}: {str(message)}")
                    random_int = randint(1, 120)
                    if (code == 429):                      
                        logger.warning("API rate limit exceeded. %s", 
                            f"Retrying in {5*API_error_count+(random_int/60)} minutes.")
                        sleep(300*API_error_count+random_int)
                    else:
                        logger.error("Unhandled API Error. \n%s %s \n%s", 
                            "The following command was not executed:",
                            f"'{function.__name__}' with arguments: {args} {kwargs}",
                            f"Retrying command in {10+(random_int/60)} minutes.",
                            exc_info=True)
                        sleep(600+random_int)
                except Exception:
                    logger.error('Unexpected error with mainIOhandler function', 
                        exc_info=True)
                    self.restartApp()
                else: 
                    self.alert.setText("")
                    sleep(handler_wait_after) # to not max google api limits
                    return
            else:
                random_int = randint(1, 120)
                logger.warning("Cannot reach internet. \n%s %s \n%s", 
                            "The following command was not executed:",
                            f"'{function.__name__}' with arguments: {args} {kwargs}",
                            f"Retrying connection in {10+(random_int/60)} minutes.")
                sleep(600+random_int)

    def queueChecker(self): 
        """threaded function that checks queue and pushes items to the handler."""
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

            if self.stopIOthread:
                break

            sleep(0.005) #free CPU briefly

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

    def keyPressEvent(self, e):  # where the fun begins
        # QT function that waits for an 'enter' keystroke
        if (e.key() == Qt.Key_Return) and (len(self.le.text()) > 0):
            input_str = self.le.text()
            self.le.clear()
            self.display.setText('"'+input_str+'"')
            self.handleInput(input_str)

    def handleInput(self, input_str):
        if input_str == "remove last barcode":
            if self.entries[0][0] != "Invalid Barcode!":
                self.queue.put(dict(function=self.sheet.delete_rows, start_index=1))  # whole barcode to the api queue
            self.rotateListUp()
        elif input_str == "retry connection":
            self.queue.put(self.getAccessToSpreadsheet)
        else:
            mat, exp_date = self.regexMatchBarcode(input_str)
            if mat != "Invalid Barcode!":
                self.queue.put(dict(function=self.sheet.insert_row, values=[input_str]))  # whole barcode to the api queue
            new_row = self.composeNewRow(mat, exp_date)
            self.rotateListDown(new_row)

    def rotateListDown(self, new_row):
        self.entries = new_row + self.entries  # add to top of list
        del self.entries[-1]  # delete last row
        self.clearLayout()
        self.updateList()

    def rotateListUp(self):
        del self.entries[0]  # delete first row
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

    def restartApp(self, current_item=None, create_dialog=False):
        do_restart = True
        if create_dialog:
            # TODO add dialog question to ask if you want to restart
            pass

        logger.info("Restarting Scanning Station")
        # TODO add dump queue to JSON

        if do_restart:
            QProcess.startDetached("python", sys.argv)

        qApp.quit()


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
