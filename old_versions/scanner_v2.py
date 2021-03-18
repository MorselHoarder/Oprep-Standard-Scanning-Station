"""
Orep Standard Scanning Station by Andrew Schult

Had much help from the ZetCode PyQt5 tutorial
Website: zetcode.com
"""

import sys
import gspread
import datetime as dt
import re
import queue
import threading
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor
from PyQt5.QtWidgets import QWidget, QApplication, QLineEdit, QLabel, QGridLayout, QLayoutItem


class BarcodeDisplay(QWidget):

    def __init__(self):
        super().__init__()

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
                              'selection-background-color: darkgray;'
                              '')
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
        self.updateList() # set up empty UI
        
        self.getPrepInvSheet() # get access to google spreadsheet
         
        self.initThread() # make separate thread for IO w/ spreadsheet
        #self.show()
        self.showMaximized() # displays the window at full res

    def sendBarcode(self): #threaded function
        while (True):
            if (self.queue.qsize() > 0):
                text = self.queue.get()
                if text == "remove last barcode":
                    self.scan.delete_rows(1)  # delete top row
                else:
                    # add a row with string
                    self.scan.insert_row(
                        [text], index=1, value_input_option='RAW')

    def initThread(self):
        # initialize separate thread to handle API queries
        self.queue = queue.Queue()
        self.thread1 = threading.Thread(target=self.sendBarcode, daemon=True)
        self.thread1.start()

    def updateList(self): # updates the list UI
        # first make a list of (x,y) positions in the widget grid
        # skip top two rows which hold widgets we don't want rotated
        positions = [(i, j) for i in range(2, 12) for j in range(3)] 

        # flatten the entries list. we want each item to be added as a widget
        ent = [a for b in self.entries for a in b]  

        for position, entry in zip(positions, ent):
            label = QLabel(entry)
            label.setStyleSheet('background-color: #3E517A;'
                                'color: #f0f1ff;'
                                'border: 2px solid #82C0CC;'
                                'border-radius: 10px;'
                                'padding: 0 8px;')
            label.setFont(self.mainFont)
            # put the new widget at the (x,y) position
            self.grid.addWidget(label, *position)

    def getPrepInvSheet(self):
        # access spreadsheet
        gc = gspread.service_account(filename='credentials.json')
        ss = gc.open_by_key(' prepped organic standard inventory key goes here')
        self.scan = ss.worksheet('Scan')  # set to object for reference later
        #self.inv = ss.worksheet('Inventory')

    def keyPressEvent(self, e):  # where the fun begins
        # QT function that waits for an 'enter' keystroke
        if (e.key() == Qt.Key_Return) and (len(str(self.le.text())) > 0):
            input_str = self.le.text()
            self.le.clear()
            self.display.setText('"'+input_str+'"')
            self.handleInput(input_str)

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
        FULL_PAT = r"^(pp[0-9]{4,5}|eph[0-9]{4}|[0-9]{4})-([0-9]{5,6}),"
        #regex = re.compile(FULL_PAT, flags=re.IGNORECASE)
        m = re.match(FULL_PAT, barcode, flags=re.I)
        #m = regex.match(barcode)
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
        #ts = ts.strftime('%m/%d/%Y %I:%M:%S %p')
        ts = ts.strftime('%m/%d/%y %H:%M')
        return ts

    def getStandardName(self, id_str):  # not used, slows down scanning
        c = self.inv.find(str(id_str))  # gets cell of standard ID
        if c:
            std_name = self.inv.cell(c.row, 2).value
        else:
            std_name = "No standard name found in the inventory!"
        return std_name

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
    app = QApplication(sys.argv)
    BD = BarcodeDisplay()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
