"""
Inventory Scanning Station by Andrew Schult

Modified from Oprep Standard Scanning Station

use version_manifest.json to check against remote manifest for update
check for update at n+random minutes
start new instance and kill the old

SVOA inventory pi
IP: 10.10.25.250 User: pi pw: svoa
"""

# stdlib
import sys
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


log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=log_format, 
                    handlers=[logging.FileHandler('errors.log')],
                    level=logging.INFO)
logger = logging.getLogger(__name__)


class BarcodeDisplay(QWidget):

    def __init__(self, spreadsheet_key, destination_sheet=None):
        super().__init__()
        self.spreadsheet_key = spreadsheet_key
        self.destination_sheet = destination_sheet
        
        self.initUI()

    def initUI(self):
        
        self.setGeometry(50, 50, 720, 480)
        self.setWindowTitle('Oprep Standard Scanning Station')
        self.setWindowIcon(QIcon('logo.png'))
        
        try:
            with open("stylesheet.qss", "r") as stylesheet:
                self.setStyleSheet(stylesheet.read())
        except:
            logger.error('Stylesheet', exc_info=True)

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

        # initialize empty list to hold data
        # UI only displays 10 rows, but keep 20 in case we rotate up
        # Part number, desc/vendor, amount?, timestamp, last time ordered?
        self.entries = [['' for y in range(4)] for x in range(20)]
        self.updateList()

        self.getAccessToSpreadsheet()
         
        # initialize separate thread to handle API queries
        self.queue = queue.Queue()
        self.IOthread = threading.Thread(target=self.queueChecker, daemon=True)
        self.IOthread.start()

        # thread to manage routine background tasks
        self.routineThread = threading.Thread(target=self.routineOps, daemon=True)
        self.routineThread.start()

        self.show()
        # self.showMaximized() # displays the window at full res


    #---------------------------------------------------------------------------
    # Logic Functions

    def keyPressEvent(self, e):  
        """Entry-point for barcode input.
        QT function that waits for an 'enter' keystroke."""
        if (e.key() == Qt.Key_Return) and (len(self.le.text()) > 0):
            input_str = self.le.text()
            self.le.clear()
            self.display.setText('"'+input_str+'"')
            self.handleInput(input_str)

    def handleInput(self, input_str):
        """This is where we figure out what to do with the input.
        Chooses the function with args to push into the queue."""
        if input_str == "remove last barcode":
            self.queue.put(dict(function=self.sheet.delete_rows, start_index=1))
            self.rotateListUp()

        elif input_str == "retry connection":
            self.getAccessToSpreadsheet()

        else:
            self.queue.put(dict(function=self.sheet.insert_row, values=[input_str]))
            new_row = self.composeNewRow(input_str)
            self.rotateListDown(new_row)

    def composeNewRow(self, input_str, item_name):
        if input_str == "Invalid Barcode!":
            new_row = [[input_str, "No Item Found", self.getTimeStamp()]]
        else:
            new_row = [[input_str, item_name,
                        self.getTimeStamp()]]
        return new_row

    def queueChecker(self): 
        """threaded function that checks queue
        and pushes items to the handler"""
        while (True):
            if (self.queue.qsize() > 0):
                dict_item = self.queue.get()
                self.gspreadHandler(**dict_item)
            sleep(0.005) #free CPU briefly
    
    def routineOps(self):
        """Handles routine operations and pushes 
        them into the queue if needed"""
        count = randint(1, 30)
        while (True):
            sleep(1)
            count += 1
            if count == 600
                # do functions
                count = 0
            

    #---------------------------------------------------------------------------
    # I/O Functions

    def isConnected(self):
        """Detects an internet connection."""
        try:
            conn = socket.create_connection(("1.1.1.1", 80))
            if conn is not None:
                conn.close()
            self.alert.setText("")
            return True
        except OSError:
            self.alert.setText("NO INTERNET CONNECTION")
        except:
            logger.error('Unexpected error with isConnected function', exc_info=True)
            qApp.quit()
        return False

    def getAccessToSpreadsheet(self):
        """Uses service account credentials to access the spreadsheet.
        Sets `self.ss` and `self.sheet` variables for operations."""
        if self.isConnected():
            try: 
                gc = gspread.service_account(filename='credentials.json')
            except:
                self.alert.setText("SERVICE ACCOUNT FAILURE")
                logger.error("Cannot access credentials and/or service account",
                            exc_info=True)
            else:
                try:
                    self.ss = gc.open_by_key(self.spreadsheet_key)
                except:
                    self.alert.setText("SPREADSHEET CONNECTION FAILURE")
                    logger.error("Cannot initialize connection to inventory sheet",
                            exc_info=True)
                else:
                    try:
                        if self.destination_sheet is not None:
                            self.sheet = self.ss.worksheet(self.destination_sheet)
                        else:
                            self.sheet = self.ss.sheet1
                    except:
                        self.alert.setText(f"WORKSHEET {self.destination_sheet} NOT FOUND")
                        logger.error(f"Cannot find sheet named {self.destination_sheet}",
                            exc_info=True)

    def gspreadHandler(self, function, *args, **kwargs):
        """Calls `function` with provided arguments.
        Main function for interacting with spreadsheet.
        Handles exceptions and API errors."""
        API_error_count = 0
        random_int = 0  
        while (True):
            if self.isConnected() is True:
                try:
                    function(*args, **kwargs)
                except gspread.exceptions.APIError as e:
                    code = e.response.json()['error']['code']
                    random_int = randint(1, 120)
                    if (code == 429):
                        API_error_count += 1
                        self.alert.setText("API rate limit exceeded")
                        logger.warning("API rate limit exceeded. %s", 
                            f"Retrying in {5*API_error_count+(random_int/60)} minutes.")
                        sleep(300*API_error_count+random_int)
                    else:
                        self.alert.setText("Unhandled API Error")
                        logger.error("Unhandled API Error. \n%s %s \n%s", 
                            "The following command was not executed:",
                            f"'{function.__name__}' with arguments: {args} {kwargs}",
                            f"Retrying command in {10+(random_int/60)} minutes.",
                            exc_info=True)
                        sleep(600+random_int)
                except:
                    logger.error('Unexpected error with gspreadHandler function', 
                        exc_info=True)
                    qApp.quit()
                else: 
                    self.alert.setText("")
                    sleep(2.5) # to not max google api limits
                    return
            else:
                random_int = randint(1, 120)
                logger.warning("Cannot reach internet. \n%s %s \n%s", 
                            "The following command was not executed:",
                            f"'{function.__name__}' with arguments: {args} {kwargs}",
                            f"Retrying connection in {10+(random_int/60)} minutes.")
                sleep(600+random_int)
                self.getAccessToSpreadsheet()


    #---------------------------------------------------------------------------
    # UI Manipulation Functions

    def clearLayout(self):  # thank mr. riverbank
        WIDGET_TOTAL = 30   # num of widgets that need deleting, can be excess
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

    def updateList(self): 
        # updates the list UI
        # first make a list of (x,y) positions in the widget grid
        # skip top two rows which hold widgets we don't want rotated
        positions = [(i, j) for i in range(2, 7) for j in range(3)] 

        # flatten the entries list
        entries = [a for b in self.entries for a in b]  

        for position, entry in zip(positions, entries):
            label = QLabel(entry)
            label.setProperty('class', 'entry')
            # put the new widget at the (x,y) position
            self.grid.addWidget(label, *position)
    
    def rotateListDown(self, new_row):
        self.entries = new_row + self.entries  # add to top of list
        del self.entries[-1]  # delete last row
        self.clearLayout()
        self.updateList()

    def rotateListUp(self):
        del self.entries[0]  # delete first row
        self.clearLayout()
        self.updateList()


    #---------------------------------------------------------------------------
    # Support Functions

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
        return dt.datetime.now().strftime('%m/%d/%y %H:%M')



def main():
    # SPREADSHEET_KEY = " prepped organic standard inventory key goes here" # 
    # SPREADSHEET_KEY = "" # test spreadsheet
    # SHEET_NAME_TO_SCAN = "Scan"

    config = configparser.ConfigParser()
    config.read('config.ini')
    SPREADSHEET_KEY = config.get('SETTINGS', 'spreadsheet_key')
    DESTINATION_SHEET = config.get('SETTINGS', 'destination_sheet')

    app = QApplication(sys.argv)
    _ = BarcodeDisplay(SPREADSHEET_KEY, DESTINATION_SHEET)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
