from .barcode import BaseBarcodeScan
from .logger import logger


SCAN_LOG_FILE = "scan_history.log"


class ScannerModel:
    """Main class that manages all internal data processing."""

    def __init__(self, barcode_scan_cls: BaseBarcodeScan, list_length: int = 20):

        self.barcode_scan_cls = barcode_scan_cls

        # initialize empty list to hold barcodes
        # UI only displays 10 rows, but keep 20 in case we rotate up
        self.entries = ["" for _ in range(list_length)]

    def _addNewEntry(self, item: BaseBarcodeScan):
        """Inserts scan item at beginning of entries list.
        Can be any object that inherits from BaseBarcodeScan"""
        self.entries.insert(0, item)
        self.entries.pop()
        self._appendScanLog(item.getScannedTimeStamp(), item.barcode_str)

    @staticmethod
    def _appendScanLog(*items):
        """Appends a csv-formatted line to the scan log."""
        s = "\n" + ",".join(items)
        try:
            with open(SCAN_LOG_FILE, "a+") as csv_file:
                csv_file.write(s)
        except FileNotFoundError:
            logger.info(f"No {SCAN_LOG_FILE} file found.")
        except PermissionError:
            logger.info(f"No write permissions for {SCAN_LOG_FILE} file.")

    def removePreviousEntry(self):
        self.entries.pop(0)

    def processNewEntry(self, input_str):
        """Returns a new barcode object to submit to the api."""
        new_barcode_scan = self.barcode_scan_cls(input_str)
        self._addNewEntry(new_barcode_scan)
        return new_barcode_scan
