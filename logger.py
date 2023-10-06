from logger_raw import Ui_MainWindow
from PyQt5.QtCore import pyqtSignal # QThread

import plc_communication as plcc
from PyQt5 import QtCore # QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow #QWidget, QInputDialog, QLineEdit
import time
import datetime

import sys
import zmq

plc_status = 0
plc_thread_exec = True # used to stop the plc reading thread

context = zmq.Context()

#  Socket to talk to server
print("Connecting to hello world server…")
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5432")


class PLCWorker(QtCore.QObject):
    # execution = False
    messaged = pyqtSignal()
    finished = pyqtSignal()

    def run(self):
        global plc_status
        global plc_thread_exec

        while plc_thread_exec:
            plc_status = plcc.is_plc_on_air()  #TODO set to 1 for testing purposes
            read = plcc.get_values()

            print("Sending plc value: {}".format(plc_status))

            try:            
                socket.send(bytes(f"{plc_status}", encoding='utf-8'))
            except:
                print("Maybe there is no one at home!")

            try:
                _ = socket.recv(2)
            except:
                print ("No message received yet")

            time.sleep(1)
            self.messaged.emit()

        print("plc communication finished")
        self.messaged.emit()
        self.finished.emit()


class MainWindow(QMainWindow):
    ui = None
    
    thread_plc = None

    def __init__(self):
        self.__thread = QtCore.QThread()
        self.__thread_plc = QtCore.QThread()

        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.open_window_init()
        self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False) # disable the X close button

        self.run_plc_check()
        self.ui.Qexit.clicked.connect(lambda: self.close())

    def run_plc_check(self):
        if not self.__thread_plc.isRunning():
            self.__thread_plc = self.__get_thread_plc()
            self.__thread_plc.start()
        else:
            print("Thread already running, killing it")
            self.__thread_plc.quit()
            time.sleep(3)
            self.__thread_plc = self.__get_thread_plc()
            self.__thread_plc.start()


    def __get_thread_plc(self):
        self.thread_plc = QtCore.QThread()
        self.plcworker = PLCWorker()
        self.plcworker.moveToThread(self.thread_plc)

        self.thread_plc.plcworker = self.plcworker

        self.thread_plc.started.connect(self.plcworker.run)
        self.plcworker.finished.connect(lambda: self.quit_thread_plc())
        self.plcworker.messaged.connect(lambda: self.update_plc_status())

        return self.thread_plc


    def quit_thread_plc(self):
        global plc_thread_exec
        plc_thread_exec = False
        self.thread_plc.quit


    def open_window_init(self):
        print("Window opened")
        
        # put some operations to perform when the window opens

   
    def close(self):
        print("")
        global plc_thread_exec
        # global log_file

        if self.thread_plc:
            plc_thread_exec = False
            self.thread_plc.quit
        time.sleep(2)

        # # write_to_file(log_file, "{}".format("--"))
        print("Window closing...")
        QApplication.quit()


    def update_status(self):
        print("")
        # Put some operations to update the visualizations of the window
        
        
    def update_plc_status(self):
        print("PLC status would now be updated!")
        # global plc_status
        # # date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

        if plc_status:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                              "background-color: rgb(85, 255, 0);")
        else:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                              "background-color: rgb(255, 0, 0);")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())