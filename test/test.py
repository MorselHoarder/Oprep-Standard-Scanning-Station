from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QMessageBox


class MainWindow(QMainWindow):

   def __init__(self):
      super().__init__()
      self.setupUI()

   def setupUI(self):
      self.setObjectName("MainWindow")
    #   self.setWindowModality(QtCore.Qt.NonModal)
      self.resize(987, 746)
      self.setMinimumSize(567, 456)
      self.setMaximumSize(987, 746)
      font = QtGui.QFont()
      font.setPointSize(9)
      self.setFont(font)


   def closeEvent(self, event):
      reply = QMessageBox.question(self, 'Quit', 'Are You Sure to Quit?', QMessageBox.No | QMessageBox.Yes)
      if reply == QMessageBox.Yes:
         event.accept()
      else:
         event.ignore()


if __name__ == "__main__":
   import sys
   app = QtWidgets.QApplication(sys.argv)
   mw = MainWindow()
   mw.show()
   sys.exit(app.exec_())