
# msgbox snippet

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