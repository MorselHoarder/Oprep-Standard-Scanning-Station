from abc import ABC, abstractmethod
import datetime as dt
import re
from typing import Dict, List


class BaseBarcodeScan(ABC):
    """Abstract barcode scan object. Barcode scan objects must inherit from this object.
    This object is not instantiable."""

    barcode_str: str
    scanned_datetime: dt.datetime

    def __init__(self, barcode_str):
        self.barcode_str = barcode_str
        self.scanned_datetime = dt.datetime.now()

    def getScannedTimeStamp(self) -> str:
        # Returns string timestamp of scanned_datetime
        return self.scanned_datetime.strftime("%m/%d/%y %H:%M")

    @abstractmethod
    def getBarcodeView(self) -> List[str]:
        """Returns a list of strings that represents the Barcode Scan information.
        To be used by the view to display barcode information."""
        pass

    @abstractmethod
    def getAPIinfo(self) -> Dict:
        """Returns a dictionary of actions and information for the API to parse."""
        pass


class OrganicPrepStandardBarcodeScan(BaseBarcodeScan):
    """Represents an oprep standard barcode scan.
    Includes regular expression validation."""

    BARCODE_PATTERN = (
        r"^(pp[0-9]{4,5}|eph[0-9]{4}|[0-9]{4,5})[A-Za-z]{0,2}-([0-9]{5,6}),"
    )
    compiled_pattern = re.compile(BARCODE_PATTERN, flags=re.IGNORECASE)

    def __init__(self, barcode_str):
        super().__init__(barcode_str)

        m = self.compiled_pattern.fullmatch(self.barcode_str)
        if m:
            self.is_matched = True
            self.standard_id = m.group(1)
            self.exp_date_str = self.formatOprepStandardDateGroupString(m.group(2))
        else:
            self.is_matched = False

    @staticmethod
    def formatOprepStandardDateGroupString(date_str):
        ls = list(date_str)

        # early bug where date was 5 digits
        if len(date_str) == 5:
            ls.insert(2, "0")

        ls.insert(2, "/")
        ls.insert(5, "/")
        return "".join(ls)

    def getBarcodeView(self) -> List:
        if self.is_matched:
            return [
                self.standard_id,
                "Expires: " + self.exp_date_str,
                "Scanned: " + self.getScannedTimeStamp(),
            ]
        else:
            return [
                "Invalid Barcode!",
                "This barcode is not from a prepped standard.",
                "Scanned: " + self.getScannedTimeStamp(),
            ]

    def getAPIinfo(self) -> Dict:
        if self.is_matched:
            return {"function": "insert_rows", "values": [self.barcode_str]}
        else:
            return None
