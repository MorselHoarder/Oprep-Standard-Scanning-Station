from PyQt5.QtWidgets import (QWidget, QPushButton, QLineEdit,
                             QInputDialog, QApplication, QDialog, QMessageBox)
from PyQt5.QtCore import QProcess, QTimer
import sys
import subprocess


class Example(QWidget):

    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.btn = QPushButton('Dialog', self)
        self.btn.move(20, 20)
        self.btn.clicked.connect(self.showMsgbox)
        # self.btn.clicked.connect(self.showDialog)

        self.le = QLineEdit(self)
        self.le.move(130, 22)

        self.setGeometry(300, 300, 450, 350)
        self.setWindowTitle('Input dialog')
        self.show()
    
    def restartApp(self):
        self.close()
        print(sys.argv)
        # QProcess.startDetached("python", ["test/test2.py"])

    def showDialog(self):
        text, ok = QInputDialog.getText(self, 'Input Dialog',
                                        'Enter your name:')

        if ok:
            self.le.setText(str(text))

    def msgbox(self, 
               label_text="""Scanning system has encountered an error.
               Restarting app in 10 seconds.""", 
               window_title="Alert", 
               timer_length_secs=10):
        """Creates a simple message dialog with cancel button that counts down.
        If cancel or escape is pressed, returns False. Otherwise timeout returns True."""
        mb = QMessageBox()
        mb.setIcon(QMessageBox.Warning)
        mb.setText(label_text)
        mb.setWindowTitle(window_title)
        mb.setStandardButtons(QMessageBox.Cancel)
        mb.setEscapeButton(QMessageBox.Cancel)
        mb.buttonClicked.connect(mb.reject)
        timer = QTimer.singleShot(timer_length_secs*1000, mb.accept)
        if mb.exec() == 1:
            return True
        else:
            return False
    
    def showMsgbox(self):
        m = self.msgbox()
        print(m)


def main():
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()



