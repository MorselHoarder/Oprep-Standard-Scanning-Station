from abc import ABC
import datetime as dt

from .utils import getTimeStamp, formatDateGroup

class BaseBarcodeScan(ABC):
    """Basic barcode scan object. Other barcodes inherit from this object."""
    barcode_str: str
    scanned_datetime: dt.datetime

    def __init__(self, barcode_str):
        self.barcode_str = barcode_str
        self.scanned_datetime = dt.datetime.now()


class OrganicPrepStandardBarcode(BaseBarcodeScan):
    """A barcode object that represents an oprep standard barcode scan."""
    def __init__(self, barcode_str):
        super().__init__(barcode_str)
        # TODO fill this out
