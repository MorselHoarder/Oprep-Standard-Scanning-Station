"""Script to count the number of scans in the scan log 
for each standard between two datetimes"""

import re
import datetime as dt

BARCODE_REGEX = re.compile(
    r"(pp[0-9]{4,5}|eph[0-9]{4}|[0-9]{4,5})[A-Za-z]{0,2}-([0-9]{5,6})",
    flags=re.IGNORECASE,
)
HISTORY_FILE = "scan_history.log"
OUTPUT_FILE = "scan_counter.log"


def get_scan_count(start_datetime, end_datetime):
    """
    Get the number of scans between two dates.
    """
    scan_count = {}
    with open(HISTORY_FILE, "r") as f:
        for line in f:
            l = line.split(",")
            date = dt.datetime.strptime(l[0], "%m/%d/%y %H:%M")
            if start_datetime <= date <= end_datetime:
                m = BARCODE_REGEX.search(l[1])
                if m:
                    barcode = m.group(1)
                    if barcode in scan_count:
                        scan_count[barcode] += 1
                    else:
                        scan_count[barcode] = 1

    with open(OUTPUT_FILE, "w") as f:
        for barcode, count in scan_count.items():
            f.write(f"{barcode},{count}\n")


if __name__ == "__main__":
    start_datetime = dt.datetime.strptime("10/26/21 04:50", "%m/%d/%y %H:%M")
    end_datetime = dt.datetime.now()
    get_scan_count(start_datetime, end_datetime)
