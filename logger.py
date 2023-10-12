from logger_raw import Ui_MainWindow
from PyQt5.QtCore import pyqtSignal # QThread
import plc_communication as plcc
from PyQt5 import QtCore # QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow #QWidget, QInputDialog, QLineEdit
import datetime
import zmq
import sys
import time
import os

logger = os.path.expanduser('~\\Documents\\LOG\\logger_EATON.csv')

cell_data = plcc.Cell_Data()

is_plc_reachable = False

def write_to_logger(filename, line):

    if os.path.isfile(filename):
        print("File exists")
    else:
        f = open(filename, "w")
        f.write("data;;;MB13;MB15;;MB110;MB120;MB130;MB150;;MB70;MB80;MB140;MB170;;MW20;MW22;;MW24;MW26;;MW28;MW30;" + "\n") #name of the PLC values
        f.write("data;;;SP_TAria;SP_TAcqua;;T_Comp1;T_Comp2;T_AriaRF;T_AriaNORF;;T_Bollitore;T_Basale;T_TerraRF;T_TerraNORF;;h_MotoComp;min_MotoComp;;h_SP_Raggiunto;min_SP_Raggiunto;;h_ScaldON;min_ScaldON;" + "\n")
        print("Logger file created: {}".format(filename))
        f.close()

    f = open(filename, "a")
    f.write(line + "\n")
    f.close()

plc_status = 0
plc_thread_exec = True # used to stop the plc reading thread

class PLCWorker(QtCore.QObject):
    messaged = pyqtSignal()
    finished = pyqtSignal()
    prev_logging_time_SHORT = 0
    prev_logging_time_LONG = 0
    logging_period_LONG = 2 # minutes
    logging_period_SHORT = 12 # seconds


    def log_EATON_state(self, prev_logging_time_SHORT, prev_logging_time_LONG, logging_period_SHORT, logging_period_LONG):

        if time.time() - prev_logging_time_SHORT >= logging_period_SHORT: # save each 10 s the value from the PLC
            try:
                read, reachable = plcc.get_values(True)
                if reachable:
                    cell_data.append_values(read[1])
                else:
                    print("Skipped because data is empty!")
            except:
                print("Error while reading from plc ")
            prev_logging_time_SHORT = time.time()

        if time.time() - prev_logging_time_LONG >= logging_period_LONG*60:  # save to logger and reset the list of values in cell_data
            try:
                logger_val_str = datetime.datetime.now().strftime("%m/%d/%Y-%H:%M:%S")+";;;"+plcc.get_logger_values(cell_data, True)
                write_to_logger(logger, logger_val_str)
            except:
                print("Error with PLC reading")
            cell_data.reset()
            prev_logging_time_LONG = time.time()

        return prev_logging_time_SHORT, prev_logging_time_LONG


    def run(self):
        global plc_status
        global plc_thread_exec
        global is_plc_reachable

        port = "5432"
        topic = 1000
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        socket.bind("tcp://*:%s" % port)
        print(f"Starting socket with port {port} and topic {topic}")

        # Initialize timers for PLC logging
        self.prev_logging_time_SHORT = time.time()
        self.prev_logging_time_LONG = time.time()

        # Check if plc is reachable:
        _, is_plc_reachable = plcc.is_plc_on_air()
        # _, is_plc_reachable = 1, False

        while plc_thread_exec:

            # PLC status
            _, is_plc_reachable = plcc.is_plc_on_air()
            # _, is_plc_reachable = 1, False
            try:
                socket.send_string("{} {}".format(topic, plc_status))
            except:
                print("Socket error: message not sent")

            # EATON logger
            self.prev_logging_time_SHORT, self.prev_logging_time_LONG = self.log_EATON_state(self.prev_logging_time_SHORT, self.prev_logging_time_LONG, self.logging_period_SHORT, self.logging_period_LONG)

            time.sleep(1)
            self.messaged.emit()

        print("PLC communication terminated")
        self.messaged.emit()
        self.finished.emit()
        print("Closing socket")
        socket.close()
        context.term()


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
        global is_plc_reachable

        print("Update plc reachable status with {}".format(is_plc_reachable))
        if is_plc_reachable:
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