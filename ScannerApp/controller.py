from PyQt5.QtWidgets import qApp

from .model import ScannerModel
from .view import BarcodeDisplay
from .api import GSpreadAPIHandler
from .barcode import OrganicPrepStandardBarcodeScan


class BarcodeScannerApp:
    """
    Main controller app. Pass in a barcode display and the api that handles interacting
    with gspread. 
    """
    def __init__(self, spreadsheet_key, sheet_name) -> None:

        self.spreadsheet_key = spreadsheet_key
        self.sheet_name = sheet_name

        self.model = ScannerModel()

        self.api = GSpreadAPIHandler(spreadsheet_key, sheet_name)
        self.barcode_obj = OrganicPrepStandardBarcodeScan

        qApp.aboutToQuit.connect(self._cleanupRoutine)

        self.view = BarcodeDisplay()
        self.view.le.returnPressed.connect(self.submitLineEditEntry)

    def submitLineEditEntry(self):
        """Gets the input from the QLineedit and submits it to the view, model, and api."""
        input_str = self.view.le.text()

        if len(input_str) == 0:
            return

        if input_str == "remove last barcode":
            self.model.removePreviousEntry()
            self.api.addItem(self.api.sheet.deleterows)
            return
        elif input_str == "retry connection":
            # TODO make this work
            return

        new_barcode_scan = self.model.processNewEntry(input_str)
        self.view.barcodeSubmitted(self.model.entries)
        self.api.addItem(new_barcode_scan)        

    def _cleanupRoutine(self) -> None:
        self.api.kill()
        self.dumpDequeToJSON()

    def show(self):
        self.view.show()

    def showMaximized(self):
        self.view.showMaximized()

        
