"""
Oprep Standard Scanning Station by Andrew Schult

Modified from Oprep Standard Scanning Station
"""

# stdlib
import sys
from time import sleep, time
import datetime as dt
import re
import queue
import threading
import socket
import traceback
import logging

# dependencies
import gspread
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QWidget, 
    QApplication, 
    QLineEdit, 
    QLabel, 
    QGridLayout, 
    QLayoutItem, 
    qApp,
)


# logger info
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=log_format, 
                    handlers=[logging.FileHandler('errors.log')],
                    level=logging.INFO)
logger = logging.getLogger(__name__)



# 1. Out here, set a global "spreadsheetCheckStartTimeSecs" to -1
# 2. set up a new handler function and put it in the queue right when the queue starts up
# 3. have the handler function do these things:
#    a. check "if spreadsheetCheckStartTimeSecs is -1, set spreadsheetCheckStartTimeSecs to current wall clock time"
#    b. sleep for 500ms
#    c. check to see if "now minus spreadsheetCheckStartTimeSecs is >= 5 minutes"
#       i. if yes, do your spreadsheet query
#       ii. if no, add this same function back to the queue again


class BarcodeDisplay(QWidget):

    def __init__(self, regex_pattern, spreadsheet_key, destination_sheet):
        super().__init__()
        self.regex_pattern = regex_pattern
        self.spreadsheet_key = spreadsheet_key
        self.destination_sheet = destination_sheet

        #self.SPREADSHEET_CHECK_START_TIME_SECS = 5 * 60
        self.SPREADSHEET_CHECK_START_TIME_SECS = 5
        self.spreadsheetCheckStartTimeSecs = -1
        
        self.initUI()

    def initUI(self):

        self.setGeometry(50, 50, 720, 480)
        self.setWindowTitle('Oprep Standard Scanning Station')
        self.setWindowIcon(QIcon('logo.png'))
        
        try:
            with open("stylesheet.qss", "r") as stylesheet:
                self.setStyleSheet(stylesheet.read())
        except:
            logger.error('Stylesheet', exc_info=1)

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

        self.getAccessToSpreadsheet()
         
        # initialize separate thread to handle API queries
        self.queue = queue.Queue()
        self.thread1 = threading.Thread(target=self.handleBarcodeQueue, daemon=True)
        self.thread1.start()

        self.queue.put(self.maybe_query_spreadsheet)

        self.compiled_pattern = re.compile(self.regex_pattern, flags=re.IGNORECASE)

        self.show()
        # self.showMaximized() # displays the window at full res

    def maybe_query_spreadsheet(self):
        if self.spreadsheetCheckStartTimeSecs == -1:
            self.spreadsheetCheckStartTimeSecs = int(time())

        sleep(0.5)

        if int(time()) - self.spreadsheetCheckStartTimeSecs >= self.SPREADSHEET_CHECK_START_TIME_SECS:
            # query sheet
            print("MY NAME IS ANDY AND I'M COOL")
            self.spreadsheetCheckStartTimeSecs = -1
            
        self.queue.put(self.maybe_query_spreadsheet)


    @staticmethod
    def isConnected():
        """Detects an internet connection."""
        try:
            conn = socket.create_connection(("1.1.1.1", 80))
            if conn is not None:
                conn.close()
            return True
        except OSError:
            pass
        except:
            logger.error('Unexpected error with isConnected function', exc_info=1)
        return False

    def getAccessToSpreadsheet(self):
        """Uses service account credentials to access the spreadsheet.
        Sets `self.ss` and `self.sheet` variables for operations."""
        if self.isConnected():
            try: 
                gc = gspread.service_account(filename='credentials.json')
            except:
                self.alert.setText("SERVICE ACCOUNT FAILURE")
                logger.error("Cannot access credentials or service account",
                            exc_info=1)
            else:
                try:
                    ss = gc.open_by_key(self.spreadsheet_key)
                    self.sheet = ss.worksheet(self.destination_sheet)
                except:
                    self.alert.setText("SPREADSHEET CONNECTION FAILURE")
                    logger.error("Cannot initialize connection to inventory sheet",
                            exc_info=1)
        else:
            self.alert.setText("NO INTERNET CONNECTION")

    def sendBarcode(self, function, *args, **kwargs):
        """Calls `function` with provided arguments.
        Handles exceptions and API errors."""
        API_error_count = 0
        while (True):
            if self.isConnected() is True:
                try:
                    function(*args, **kwargs)
                except gspread.exceptions.APIError as e:
                    code = e.response.json()['error']['code']
                    status = e.response.json()['error']['status']
                    print("API error code:", code, status)
                    if (code == 429):
                        API_error_count += 1
                        self.alert.setText("API rate limit exceeded")
                        logger.warning("API rate limit exceeded. %s", 
                            f"Retrying in {5*API_error_count} minutes.")
                        sleep(300*API_error_count)
                    else:
                        self.alert.setText("Unhandled API Error")
                        logger.error("Unhandled API Error. \n%s %s \n%s", 
                            "The following command was not executed:",
                            f"'{function.__name__}' with arguments: {args} {kwargs}",
                            "Retrying command in 10 minutes.",
                            exc_info=1)
                        sleep(600)
                except:
                    logger.error('Unexpected error with sendBarcode function', exc_info=1)
                    qApp.quit()
                else: 
                    self.alert.setText("")
                    sleep(2.5) # to not max google api limits
                    return
            else:
                self.alert.setText("NO INTERNET CONNECTION")
                logger.warning("Cannot reach internet. \n%s %s \n%s", 
                            "The following command was not executed:",
                            f"'{function.__name__}' with arguments: {args} {kwargs}",
                            "Retrying connection in 10 minutes.")
                sleep(600)
                self.getAccessToSpreadsheet()

    def handleBarcodeQueue(self): 
        #threaded function that checks queue 
        while (True):
            if (self.queue.qsize() > 0):
                dict_item = self.queue.get()
                if type(dict_item) is dict:
                    self.sendBarcode(**dict_item)
                else:
                    dict_item()
            sleep(0.005) #free CPU briefly

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
        """This is where we figure out what to do with the input.
        Chooses the function with args to push into the queue."""
        if input_str == "remove last barcode":
            if self.entries[0][0] != "Invalid Barcode!":
                self.queue.put(dict(function=self.sheet.delete_rows, start_index=1))
            self.rotateListUp()

        elif input_str == "retry connection":
            if self.isConnected() is True:
                self.alert.setText("")

        else:
            mat, exp_date = self.regexMatchBarcode(input_str)
            if mat != "Invalid Barcode!":
                self.queue.put(dict(function=self.sheet.insert_row, values=[input_str]))
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


def main():
    # pattern ignores case by default
    BARCODE_PATTERN = r"^(pp[0-9]{4,5}|eph[0-9]{4}|[0-9]{4,5})[A-Za-z]{0,2}-([0-9]{5,6}),"
    # SPREADSHEET_KEY = " prepped organic standard inventory key goes here"
    SPREADSHEET_KEY = "" # test spreadsheet
    SHEET_NAME_TO_SCAN = "Scan"

    app = QApplication(sys.argv)
    _ = BarcodeDisplay(BARCODE_PATTERN, SPREADSHEET_KEY, SHEET_NAME_TO_SCAN)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
