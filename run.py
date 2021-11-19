import sys

from PyQt5.QtWidgets import QApplication

from ScannerApp.controller import BarcodeScannerApp


SPREADSHEET_KEY = "11Y3oufYpwWanKRB0KzxsrhkqErfPgak-LylKCt6a4i0"  # test spreadsheet
# SPREADSHEET_KEY = "1c0J8E4Z96jPnu2hqgwEEXzWmhldv-BHCU66rwUCrWw0" # Prep Inventory
SHEET_NAME_TO_SCAN = "Scan"


def main():
    app = QApplication(sys.argv)
    bsa = BarcodeScannerApp(SPREADSHEET_KEY, SHEET_NAME_TO_SCAN)
    bsa.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
