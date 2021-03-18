"""
Orep Standard Scanning Station by Andrew Schult

Had much help from the ZetCode PyQt5 tutorial
Website: zetcode.com
"""

import sys
import gspread
from time import sleep, time
import datetime as dt
import re
import queue
import threading
from PyQt5.QtCore import Qt, QObject, QThread
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor
from PyQt5.QtWidgets import (QWidget, QApplication, QLineEdit, QLabel, 
    QGridLayout, QLayoutItem)


def timeit(method):
    def timed(*args, **kw):
        ts = time()
        result = method(*args, **kw)
        te = time()        
        print(method.__name__, (te - ts) * 1000)
        return result
    return timed

class BarcodeHandler(QObject):
    def __init__(self, queue, spreadsheet_key, destination_sheet):
        super().__init__()
        self.queue = queue

        # get access to google spreadsheet
        gc = gspread.service_account(filename='credentials.json')
        ss = gc.open_by_key(spreadsheet_key)
        self.sheet = ss.worksheet(destination_sheet)

    def handleBarcodeQueue(self): 
        #threaded function that checks queue and loads correct function. 
        while (True):
            if (self.queue.qsize() > 0):
                text = self.queue.get()
                if text == "remove last barcode":
                    self.sendBarcode(self.sheet.delete_rows, start_index=1)
                else:
                    self.sendBarcode(self.sheet.insert_row, values=[text])
            sleep(0.01)

    def sendBarcode(self, function, *args, **kwargs):
        """Calls `function` with provided arguments `*args` and `**kwargs`.
        Handles exceptions and API errors."""
        API_error_count = 0
        while True:
            try:
                function(*args, **kwargs)
            except gspread.exceptions.APIError as e:
                code = e.response.json()['error']['code']
                status = e.response.json()['error']['status']
                print("API error code:", code, status)
                if (code == 429):
                    API_error_count += 1
                    print("API rate limit exceeded. Trying again in",
                          f"{5*API_error_count} minutes.")
                    sleep(300*API_error_count)
                else:
                    print(e.response.json()['error']['message'])
            except Exception as e:
                raise(e)
            else: 
                sleep(2.5) # to not max google api limits
                return

class BarcodeDisplay(QWidget):

    def __init__(self, regex_pattern, spreadsheet_key, destination_sheet):
        super().__init__()
        self.regex_pattern = re.compile(regex_pattern, flags=re.IGNORECASE)
        self.SPREADSHEET_KEY = spreadsheet_key
        self.DESTINATION_SHEET = destination_sheet

        self.initUI()

    def initUI(self):

        self.setGeometry(50, 50, 720, 480)
        self.setWindowTitle('Oprep Standard Scanning Station')
        self.setWindowIcon(QIcon('logo.png'))
        self.setStyleSheet('background-color: #030027;')
        self.mainFont = QFont('Roboto Mono')

        self.grid = QGridLayout(self)
        self.setLayout(self.grid)

        self.le = QLineEdit(self)
        self.le.setStyleSheet('color: #031D44;'
                              'border: 1px solid transparent #6D8EA0;'
                              'border-radius: 5px;'
                              'padding: 0 8px;'
                              'background: #f0f1ff;'
                              'selection-background-color: darkgray;')
        self.display = QLabel("No Barcode Yet")
        self.display.setStyleSheet("font-size: 12pt; color: #f0f1ff;")
        self.display.setFont(self.mainFont)

        l1 = QLabel("Scan here:")
        l1.setStyleSheet("font-size: 12pt; font-weight: bold; color: #f0f1ff")
        l1.setFont(self.mainFont)
        l2 = QLabel("Previous scan: ")
        l2.setStyleSheet("font-size: 12pt; font-weight: bold; color: #f0f1ff")
        l2.setFont(self.mainFont)

        self.grid.addWidget(l1, 0, 0)
        self.grid.addWidget(l2, 1, 0)
        self.grid.addWidget(self.le, 0, 1)
        self.grid.addWidget(self.display, 1, 1)

        # initialize empty list to hold barcodes
        # UI only displays 10 rows, but keep 20 in case we rotate up
        self.entries = [['' for y in range(3)] for x in range(20)]
        self.updateList()
         
        # initialize separate thread to handle API queries
        self.queue = queue.Queue()
        self.thread1 = QThread()
        self.worker1 = BarcodeHandler(self.queue, self.SPREADSHEET_KEY, 
                                      self.DESTINATION_SHEET)
        self.worker1.moveToThread(self.thread1)
        self.thread1.started.connect(self.worker1.handleBarcodeQueue)
        self.thread1.start()

        self.show()
        # self.showMaximized() # displays the window at full res

    @timeit
    def updateList(self): 
        # updates the list UI
        # first make a list of (x,y) positions in the widget grid
        # skip top two rows which hold widgets we don't want rotated
        positions = [(i, j) for i in range(2, 12) for j in range(3)] 

        # flatten the entries list. we want each item to be added as a widget
        entries = [a for b in self.entries for a in b]  

        for position, entry in zip(positions, entries):
            label = QLabel(entry)
            label.setStyleSheet('background-color: #3E517A;'
                                'color: #f0f1ff;'
                                'border: 2px solid #82C0CC;'
                                'border-radius: 10px;'
                                'padding: 0 8px;')
            label.setFont(self.mainFont)
            # put the new widget at the (x,y) position
            self.grid.addWidget(label, *position)

    @timeit
    def keyPressEvent(self, e):  # where the fun begins
        # QT function that waits for an 'enter' keystroke
        if (e.key() == Qt.Key_Return) and (len(str(self.le.text())) > 0):
            input_str = self.le.text()
            self.le.clear()
            self.display.setText('"'+input_str+'"')
            self.handleInput(input_str)

    @timeit
    def handleInput(self, input_str):
        if input_str == "remove last barcode":
            if self.entries[0][0] != "Invalid Barcode!":
                self.queue.put(input_str)  # whole barcode to the api queue
            self.rotateListUp()
        else:
            mat, exp_date = self.regexMatchBarcode(input_str)
            if mat != "Invalid Barcode!":
                self.queue.put(input_str)  # whole barcode to the api queue
            new_row = self.composeNewRow(mat, exp_date)
            self.rotateListDown(new_row)

    @timeit
    def rotateListDown(self, new_row):
        self.entries = new_row + self.entries  # add to top of list
        del self.entries[-1]  # delete last row
        self.clearLayout()
        self.updateList()

    @timeit
    def rotateListUp(self):
        del self.entries[0]  # delete first row
        self.clearLayout()
        self.updateList()

    @timeit
    def regexMatchBarcode(self, barcode):
        m = self.regex_pattern.fullmatch(barcode)
        if m:
            mat = m.group(1)
            exp_date = self.formatDateGroup(m.group(2))
        else:
            mat = "Invalid Barcode!"
            exp_date = "This barcode is not from a prepped standard."
        return mat, exp_date

    @timeit
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

    # def getStandardName(self, id_str):  # not used, slows down scanning
    #     c = self.inv.find(str(id_str))  # gets cell of standard ID
    #     if c:
    #         std_name = self.inv.cell(c.row, 2).value
    #     else:
    #         std_name = "No standard name found in the inventory!"
    #     return std_name

    @timeit
    def clearLayout(self):  # thank mr. riverbank
        WIDGET_TOTAL = 30  # num of widgets that need deleting
        TOP_ROW = 4  # num of widgets in front to keep
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
    BARCODE_PATTERN = r"^(pp[0-9]{4,5}|eph[0-9]{4}|[0-9]{4,5})-([0-9]{5,6}),"
    # SPREADSHEET_KEY = " prepped organic standard inventory key goes here"
    SPREADSHEET_KEY = "" # test spreadsheet
    SHEET_NAME_TO_SCAN = "Scan"

    app = QApplication(sys.argv)
    _ = BarcodeDisplay(BARCODE_PATTERN, SPREADSHEET_KEY, SHEET_NAME_TO_SCAN)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
