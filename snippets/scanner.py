"""
Orep Standard Scanning Station by Andrew Schult

Had much help from the ZetCode PyQt5 tutorial
Website: zetcode.com
"""

# stdlib
import sys
import configparser
from collections import deque
import json

# other files
from ScannerApp.utils import (
    formatDateGroup, 
    getTimeStamp, 
    isConnected, 
    JSONEncoderWithFunctions)
from ScannerApp.api import DequeWorker
from ScannerApp.barcode import OrganicPrepStandardBarcode
from ScannerApp.logger import logger
from ScannerApp.exceptions import AccessSpreadsheetError

# dependencies
import gspread
from PyQt5.QtCore import (
    Qt, 
    QObject,
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


SCRIPT_VERSION = "1.0.0"
DEQUE_DUMP_FILE = "deque_dump.json"
DEQUE_ITEMS_KEY = "deque_items"


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

        # TODO change this deque to a deque for appending functionality
        self.deque = deque.Deque()
        self.threadpool = QThreadPool()

        self.IOthreadWorker = DequeWorker(self.deque)
        self.IOthreadWorker.signals.finished.connect(self.close)
        self.threadpool.start(self.IOthreadWorker)

        # get initial access to spreadsheet
        self.deque.put(dict(function=self.getAccessToSpreadsheet))

        # TODO get this to read properly, needs self.sheet populated. 
        # self.readDequeFromJSON()

        self._refresh_spreadsheet_timer = QTimer()
        self._refresh_spreadsheet_timer.setInterval(10 * 60 * 1000) # every 10 minutes in msecs
        self._refresh_spreadsheet_timer.timeout.connect(self._refreshSpreadsheet)
        self._refresh_spreadsheet_timer.start()



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
        Puts `getAccessToSpreadsheet` into deque."""
        self.deque.put(dict(function=self.getAccessToSpreadsheet))

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
                self.deque.put(dict(function=self.sheet.delete_rows, start_index=1))
            self.rotateListUp()
        elif input_str == "retry connection":
            self.deque.put(self.getAccessToSpreadsheet)
        else:
            mat, exp_date = self.regexMatchBarcode(input_str)
            if mat != "Invalid Barcode!":
                self.deque.put(dict(function=self.sheet.insert_row, values=[input_str]))
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

    def composeNewRow(self, id_std, exp_date):
        if id_std == "Invalid Barcode!":
            new_row = [[id_std, exp_date, "Scanned: " + getTimeStamp()]]
        else:
            new_row = [[id_std, "Expires: " + exp_date,
                        "Scanned: " + getTimeStamp()]]
        return new_row

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

    def combineDequeItem(self, function, *args, **kwargs):
        if args:
            return list(function, *args)
        else:
            return dict(kwargs, function=function)

    def readDequeFromJSON(self):
        "Gets any deque items from deque_dump.json and puts them into the deque."
        try: 
            with open(DEQUE_DUMP_FILE) as deque_dump:
                data_dict = json.load(deque_dump)
        except FileNotFoundError:
            logger.info("No deque_dump.json file found.")
            return
        
        for item in data_dict[DEQUE_ITEMS_KEY]:
            if isinstance(item, dict):
                func_name = item.get('function')
                if func_name == 'insert_row':
                    self.deque.put(dict(function=self.sheet.insert_row, 
                                        values=item.get('values')))
                elif func_name == 'delete_rows':
                    self.deque.put(dict(function=self.sheet.delete_rows, 
                                        start_index=item.get('start_index')))
        
        # clear old values
        data_dict[DEQUE_ITEMS_KEY] = ''
        with open(DEQUE_DUMP_FILE, "w") as deque_dump:
            json.dump(data_dict, deque_dump, indent=2)

    def dumpDequeToJSON(self, current_item=None):
        "Puts every item left in the deque into json file"
        data_dict = dict(version=SCRIPT_VERSION)

        item_list = []
        if current_item is not None:
            item_list.append(current_item)

        while (True):
            try:
                item = self.deque.get(block=False)
            except deque.Empty:
                break 
            else:
                item_list.append(item)

        data_dict[DEQUE_ITEMS_KEY] = item_list
        
        with open(DEQUE_DUMP_FILE, "w") as deque_dump:
            json.dump(data_dict, deque_dump, indent=2, cls=JSONEncoderWithFunctions)

        logger.info("Deque dumped to JSON")

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
        self.dumpDequeToJSON()



def main():
    # SPREADSHEET_KEY = "1c0J8E4Z96jPnu2hqgwEEXzWmhldv-BHCU66rwUCrWw0"
    SPREADSHEET_KEY = "11Y3oufYpwWanKRB0KzxsrhkqErfPgak-LylKCt6a4i0" # test spreadsheet
    SHEET_NAME_TO_SCAN = "Scan"

    app = QApplication(sys.argv)
    _ = BarcodeDisplay(BARCODE_PATTERN, SPREADSHEET_KEY, SHEET_NAME_TO_SCAN)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
