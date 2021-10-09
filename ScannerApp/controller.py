from PyQt5.QtWidgets import qApp
from PyQt5.QtCore import pyqtSlot

from .model import ScannerModel
from .view import BarcodeDisplay
from .api import GSpreadAPIHandler
from .barcode import OrganicPrepStandardBarcodeScan


class BarcodeScannerApp:
    """
    Main controller app. Pass in a barcode display and the api that handles interacting
    with gspread.
    """

    def __init__(
        self,
        spreadsheet_key,
        sheet_name,
        model=ScannerModel,
        view=BarcodeDisplay,
        barcode_cls=OrganicPrepStandardBarcodeScan,
        api=GSpreadAPIHandler,
    ) -> None:

        self.model = model(barcode_cls)

        self.api = api(spreadsheet_key, sheet_name)

        qApp.aboutToQuit.connect(self._cleanupRoutine)

        self.view = view()
        self.view.connectUserInputSlot(self.receiveUserInput)
        self.view.updateList(self.model.entries)

    def receiveUserInput(self):
        """Slotted function triggered by the view.
        Gets user input from the view and submits it to the view, model, and api."""
        input_str = self.view.getUserInput()

        if len(input_str) == 0:
            return

        if input_str == "remove last barcode":
            self.model.removePreviousEntry()
            self.api.addItem(dict(function="delete_row", index=1))
        elif input_str == "retry connection":
            self.api.addItem(dict(function="getAccessToSpreadsheet"))
        else:
            new_barcode_scan = self.model.processNewEntry(input_str)
            self.api.addItem(new_barcode_scan.getAPIinfo())

        self.view.barcodeSubmitted(self.model.entries)

    def _cleanupRoutine(self) -> None:
        self.api.kill()
        # self.dumpDequeToJSON()

    def show(self):
        self.view.show()

    def showMaximized(self):
        self.view.showMaximized()
