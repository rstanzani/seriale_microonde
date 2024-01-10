from logger_raw import Ui_MainWindow
from PyQt5.QtCore import pyqtSignal # QThread
import plc_communication as plcc
from PyQt5 import QtCore # QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow #QWidget, QInputDialog, QLineEdit, QFileDialog
import datetime
import sys
import time
import os
import plc_socket as plcsk
import zmq
import rf_utils as rfu

#TODO list:
# (001) - enable/disable simulated values
# (002) - enable/disable plc reading

class PLCWorker(QtCore.QObject):
    messaged = pyqtSignal()
    finished = pyqtSignal()
    logger = os.path.expanduser('~\\Documents\\LOG\\logger_EATON.csv')
    cell_data = plcc.Cell_Data()
    prev_log_time_SHORT = 0
    prev_log_time_LONG = 0
    log_period_LONG = 12 # minutes
    log_period_SHORT = 12 # seconds
    plc_status = 0
    is_plc_reachable = False
    plc_thread_exec = True # used to stop the plc reading thread
    timestamp_rf_check = 0

    # Variables for logging RF values
    rf_log = rfu.RFdataLists()

    # Publisher socket (to send: PLC_ON_AIR value)
    topic = 1001
    context = None
    socket = None

    # Subscriber socket (to receive: RF values)
    topic_sbr = 2002
    context_sbr = None
    socket_sbr = None

    def write_to_logger(self, filename, line):
        if os.path.isfile(filename):
            print("File exists")
        else:
            f = open(filename, "w")
            f.write("data;;;W;I;T;MB13;MB15;;MB110;MB120;MB130;MB150;;MB70;MB80;MB140;MB170;;MW20;MW22;;MW24;MW26;;MW28;MW30;" + "\n") #name of the PLC values
            f.write("data;;;Potenza;Corrente;TempDispositivo;SP_TAria;SP_TAcqua;;T_Comp1;T_Comp2;T_AriaRF;T_AriaNORF;;T_Bollitore;T_Basale;T_TerraRF;T_TerraNORF;;h_MotoComp;min_MotoComp;;h_SP_Raggiunto;min_SP_Raggiunto;;h_ScaldON;min_ScaldON;" + "\n")
            print("Logger file created: {}".format(filename))
            f.close()

        f = open(filename, "a")
        f.write(line + "\n")
        f.close()


    def log_on_file(self, prev_log_time_SHORT, prev_log_time_LONG):
        '''Save of the log file for both EATON and the few RF values that are needed.'''

        # Read RF values from socket
        if time.time() >= self.timestamp_rf_check + self.log_period_SHORT:  # Important: keep this reading frequency lower than the writing one to minimize reading errors from zmq library
            try:
                string = self.socket_sbr.recv(zmq.NOBLOCK) 
                self.rf_log.append_values(string.split()[1:])

                # print(" power current temp: {} {} {}".format(self.rf_log.forward_Power, self.rf_log.current, self.rf_log.temperature) )
            except zmq.error.Again:
                print("EAGAIN error from zmq (maybe no message from publisher).")
            except:
                print("No message from RF socket.")
            self.timestamp_rf_check = time.time()

        # Read plc values
        if time.time() - prev_log_time_SHORT >= self.log_period_SHORT: # save each tot s the value from the PLC
            try:
                read, reachable = plcc.get_values(simulate=False) # Simulate values (for testing outside the lab)
                if reachable:
                    self.cell_data.append_values(read)
                else:
                    print("Skipped because data is empty!")
            except:
                print("Error while reading from plc ")
            prev_log_time_SHORT = time.time()

        # Save values on the log file and reset lists
        if time.time() - prev_log_time_LONG >= self.log_period_LONG*60:  # save to logger and reset the list of values in cell_data
            try:
                logger_val_str = datetime.datetime.now().strftime("%m/%d/%Y-%H:%M:%S")+";;;"+ rfu.get_logger_values(self.rf_log)+plcc.get_logger_values(self.cell_data, False) # TODO (001)
                self.write_to_logger(self.logger, logger_val_str)
            except:
                print("Error with PLC reading")
            self.cell_data.reset()
            self.rf_log.reset()
            prev_log_time_LONG = time.time()

        return prev_log_time_SHORT, prev_log_time_LONG


    def run(self):

        # Initialize publisher context
        self.context, self.socket = plcsk.publisher("5432", self.topic)

        # Open subscriber socket (used for RF values)
        self.context_sbr, self.socket_sbr = plcsk.subscriber("5433", str(self.topic_sbr))

        # Initialize timers for PLC logging
        self.prev_log_time_SHORT = time.time()
        self.prev_log_time_LONG = time.time()

        # Check if plc is reachable:
        _, self.is_plc_reachable = plcc.is_plc_on_air()
        # _, self.is_plc_reachable = 1, True   # TODO 002

        self.timestamp_rf_check = time.time()

        while self.plc_thread_exec:

            # Write PLC status on socket
            self.plc_status, self.is_plc_reachable = plcc.is_plc_on_air()
            # print("## plc_status is {}".format(self.plc_status))
            # self.plc_status, self.is_plc_reachable = 1, True # TODO 002
            try:
                self.socket.send_string("{} {}".format(self.topic, self.plc_status))
                # print(f"Send socket msg with plc_status: {self.plc_status}")
            except:
                print("Socket error: message not sent")

            # Add values to log or save on log file (depending on the timestamp)
            self.prev_log_time_SHORT, self.prev_log_time_LONG = self.log_on_file(self.prev_log_time_SHORT, self.prev_log_time_LONG)

            time.sleep(0.5)
            self.messaged.emit()

        print("PLC communication terminated")
        self.messaged.emit()
        self.finished.emit()
        self.socket.close()
        self.context.term()
        self.socket_sbr.close()
        self.context_sbr.term()
        print("Socket closed")


class MainWindow(QMainWindow):
    ui = None
    thread_plc = None
    plcworker = None

    def __init__(self):
        self.__thread = QtCore.QThread()
        self.__thread_plc = QtCore.QThread()

        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.plcworker = PLCWorker()
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
        self.plcworker.moveToThread(self.thread_plc)

        self.thread_plc.plcworker = self.plcworker

        self.thread_plc.started.connect(self.plcworker.run)
        self.plcworker.finished.connect(lambda: self.quit_thread_plc())
        self.plcworker.messaged.connect(lambda: self.update_plc_status())
        return self.thread_plc


    def quit_thread_plc(self):
        self.plcworker.plc_thread_exec = False
        self.thread_plc.quit


    def open_window_init(self):
        print("Window opened")
        # put some operations to perform when the window opens


    def close(self):

        if self.thread_plc:
            self.plcworker.plc_thread_exec = False
            self.thread_plc.quit
        time.sleep(2)
        print("Window closing...")
        QApplication.quit()


    def update_status(self):
        print("")
        # Put some operations to update the visualizations of the window


    def update_plc_status(self):
        _translate = QtCore.QCoreApplication.translate
        if self.plcworker.is_plc_reachable:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                              "background-color: rgb(85, 255, 0);")
            self.ui.QPLCInfo.setText(_translate("MainWindow", "Active"))
        else:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                              "background-color: rgb(255, 0, 0);")
            self.ui.QPLCInfo.setText(_translate("MainWindow", "Inactive"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())