from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QWidget, qApp
from time import sleep


class MainWindow(QWidget):

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

      qApp.aboutToQuit.connect(self.cleanupStuff)


   def closeEvent(self, event):
      reply = QMessageBox.question(self, 'Quit', 'Are You Sure to Quit?', QMessageBox.No | QMessageBox.Yes)
      if reply == QMessageBox.Yes:
         event.accept()
      else:
         event.ignore()
      print("closeEvent finished")

   def cleanupStuff(self):
      print("doing cleanup stuff")
      sleep(2)
      print("cleanup finished")


if __name__ == "__main__":
   import sys
   app = QtWidgets.QApplication(sys.argv)
   mw = MainWindow()
   mw.show()
   sys.exit(app.exec_())
   