from ScannerApp.logger import logger

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QLineEdit, QLabel, QGridLayout


class BarcodeDisplay(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):

        self.setGeometry(50, 50, 720, 480)
        self.setWindowTitle("Oprep Standard Scanning Station")
        self.setWindowIcon(QIcon("logo.png"))

        try:
            with open("stylesheet.qss", "r") as stylesheet:
                self.setStyleSheet(stylesheet.read())
        except FileNotFoundError:
            logger.warning("stylesheet.qss not found in parent directory")

        self.grid = QGridLayout(self)
        self.setLayout(self.grid)

        self.le = QLineEdit(self)
        self.le.setProperty("class", "inputField")

        self.display = QLabel("No Barcode Yet")
        self.display.setProperty("class", "display")

        self.alert = QLabel("")
        self.alert.setProperty("class", "alert")
        self.alert.setWordWrap(True)
        self.alert.setAlignment(Qt.AlignCenter)

        l1 = QLabel("Scan here:")
        l1.setProperty("class", "headers")
        l2 = QLabel("Previous scan: ")
        l2.setProperty("class", "headers")

        self.grid.addWidget(l1, 0, 0)
        self.grid.addWidget(l2, 1, 0)
        self.grid.addWidget(self.le, 0, 1)
        self.grid.addWidget(self.display, 1, 1)
        self.grid.addWidget(self.alert, 0, 2, 2, 1)

    def updateList(self, entries_list):
        # updates the list UI
        # first make a list of (x,y) positions in the widget grid
        # skip top two rows which hold widgets we don't want rotated
        positions = [(i, j) for i in range(2, 12) for j in range(3)]

        # flatten the entries list
        entries = []
        for item in entries_list:
            try:
                entries.extend(item.getBarcodeView())
            except AttributeError:
                entries.extend(["", "", ""])

        for position, entry in zip(positions, entries):
            label = QLabel(entry)
            label.setProperty("class", "entry")
            # put the new widget at the (x,y) position
            self.grid.addWidget(label, *position)

    def clearLayout(self):  # thank mr. riverbank
        WIDGET_TOTAL = 30  # num of widgets that need deleting
        TOP_ROW = 5  # num of widgets in front to keep
        i = 0
        while i < WIDGET_TOTAL:
            i += 1
            item = self.grid.takeAt(TOP_ROW)
            if not item:
                continue
            w = item.widget()
            if w:
                w.deleteLater()

    def barcodeSubmitted(self, entries_list):
        """Handles changing of the view when a barcode is submitted."""
        text = self.le.text()
        self.le.clear()
        self.display.setText('"' + text + '"')

        self.clearLayout()
        self.updateList(entries_list)

    def connectUserInputSlot(self, slot_func):
        self.le.returnPressed.connect(slot_func)

    def getUserInput(self):
        return self.le.text()
