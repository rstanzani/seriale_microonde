from PyQt5 import QtCore # QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow #QWidget, QInputDialog, QLineEdit
import time
import read_csv as rcsv
import serial_RW as srw
from UI_raw import Ui_MainWindow
import sys
from PyQt5.QtCore import pyqtSignal # QThread


class RFdata:
    Temperature = "ND"
    PLL = "ND"
    Current = "ND"
    Voltage = "ND"
    Reflected_Power= "ND"
    Forward_Power= "ND"
    PWM = "ND"
    On_Off = "ND"
    Enable_foldback = "ND"
    Foldback_in = "ND"
    Error = "No error"

    def set_values(self, rf_dict):
        self.Temperature = rf_dict["Temperature"]
        self.PLL = rf_dict["PLL"]
        self.Current = rf_dict["Current"]
        self.Voltage = rf_dict["Voltage"]
        self.Reflected_Power = rf_dict["Reflected Power"]
        self.Forward_Power = rf_dict["Forward Power"]
        self.PWM = rf_dict["PWM"]
        self.On_Off = rf_dict["On Off"]
        self.Enable_foldback = rf_dict["Enable foldback"]
        self.Foldback_in = rf_dict["Foldback in"]
        self.Error = rf_dict["Error"]


class Worker(QtCore.QObject):

    rf_data = RFdata()
    execution = False

    duration = 0
    freq_list = []
    power_list = []
    status = {"Temperature":"ND","PLL":"ND","Current":"ND","Voltage":"ND","Reflected Power":"ND",
              "Forward Power":"ND", "PWM":"ND", "On Off":"ND", "Enable foldback":"ND", "Foldback in":"ND", "Error":"No error"}

    messaged = pyqtSignal(object)
    finished = pyqtSignal()
    duration = 0
    freq_list = []
    power_list = []

    def stop_execution(self):
        print("Stopped execution")
        self.execution = False

    def start_execution(self):
        print("Started execution")
        self.execution = True

    def give_values(self, duration, freq_list, power_list):
        print("Associating values")
        self.duration = duration
        self.freq_list = freq_list
        self.power_list = power_list
        print("The values are: {} {} {}".format( self.duration, self.freq_list, self.power_list))

    def run(self):
        self.start_execution()
        # global execution
        print("Opening connection with RF...")
        ser = srw.connect_serial("COM9")
        # Initialize
        index = 0
        print("Index is: {}".format(index))
        next_time = self.duration[0]
        freq = self.freq_list[0]
        power = self.power_list[0]

        print("Next time: {}".format(next_time))
        srw.send_cmd_string(ser,"ON")
        srw.send_cmd_string(ser,"PWR", power)
        srw.send_cmd_string(ser,"FREQ", freq)
        self.status = srw.read_param(ser, self.status, "STATUS", False)

        # Start the main functions
        timestamp = time.time()
        min_refresh = 1
        init_time = time.time()

        while self.execution:
            if time.time() >= timestamp + min_refresh: # minimum refresh period
                print("Send a command...")
                if time.time()-init_time >= next_time:

                    index += 1
                    index = index % len(self.duration)  # set to 0 if is the last line in the csv

                    next_time = next_time + self.duration[index]
                    power = self.power_list[index]
                    freq = self.freq_list[index]

                    if index == 0:
                        init_time = time.time()
                        next_time = self.duration[index]

                    srw.send_cmd_string(ser,"PWR", power)
                    srw.send_cmd_string(ser,"FREQ", freq)
                self.status = srw.read_param(ser, self.status, "STATUS", False)
                self.status = srw.read_param(ser, self.status, "FLDBCK_READ", False)
                self.rf_data.set_values(self.status)
                self.messaged.emit(self.rf_data)
                timestamp = time.time()

        # Soft turn off
        print("\nStart soft shut down...")
        srw.send_cmd_string(ser,"OFF")
        srw.send_cmd_string(ser,"PWM", 0)
        srw.empty_buffer(ser, self.status, wait=1)
        self.status = srw.read_param(ser, self.status, "STATUS")
        
        # Close ports
        ser.close()
        self.rf_data.set_values(self.status)
        self.messaged.emit(self.rf_data)
        self.finished.emit()


class MainWindow(QMainWindow):
    ui = None
    duration = 0
    freq_list = []
    power_list = []
    error = ""
    msg = ""
    status = {"Temperature":"ND","PLL":"ND","Current":"ND","Voltage":"ND","Reflected Power":"ND",
              "Forward Power":"ND", "PWM":"ND", "On Off":"ND", "Enable foldback":"ND", "Foldback in":"ND", "Error":"No error"}
    error_history = []
    timestamp_old = 0
    execution = True
    worker = None
    thread = None

    def __init__(self):

        self.__thread = QtCore.QThread()

        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.QOpen_CSV.clicked.connect(lambda:  self.open_file("Open_CSV"))
        self.ui.Qexit.clicked.connect(lambda: self.close())
        self.ui.Qplay.clicked.connect(lambda: self.play_execution())
        # self.ui.Qpause.clicked.connect(lambda: self.pause_execution())
        self.ui.Qstop.clicked.connect(lambda: self.stop_execution())


    def run_long_task(self):
        if not self.__thread.isRunning():
            self.__thread = self.__get_thread()
            self.__thread.start()


    def __get_thread(self):
        self. thread = QtCore.QThread()
        self.worker = Worker()
        self.worker.give_values(self.duration, self.freq_list, self.power_list)
        self.worker.moveToThread(self.thread)

        # this is essential when worker is in local scope!
        self.thread.worker =  self.worker

        self.thread.started.connect( self.worker.run)
        self.worker.finished.connect(lambda: self.quit_and_disable_buttons())

        # worker.progressed.connect(lambda value: update_progress(self.ui.progressBar, value))   #for a progress bar
        # worker.messaged.connect(lambda msg: update_status(self.statusBar(), msg))
        self.worker.messaged.connect(lambda msg: update_status(msg))

        return self.thread


    def quit_and_disable_buttons(self):
        self.thread.quit
        self.enablePlayButton()
        self.disableStopButton()
        self.disablePauseButton()


    def save_error_log(self):
        to_add = False
        if self.status["Error"] != "No error":
            if len(self.error_history) != 0:
                if self.error_history[-1][1] != self.status["Error"]:
                    print("Add: new value")
                    to_add = True
                elif time.time()-self.error_history[-1][0] >= 60:
                    print("Add with {} seconds!".format(time.time()-self.error_history[-1][0]))
                    to_add = True
            else:
                print("Add: first elem")
                to_add = True
            if to_add:
                self.error_history.append([time.time(), self.status['Error']])
        self.status["Error"] = "No error"


    def open_file(self, button_name):
        # Reads the file path from the prompt
        self.disablePlayButton()
        file_type = button_name.split("_")[1]
        path = ""
        opened_path, _ = QFileDialog.getOpenFileName(None, "Open the {} file".format(file_type), path, "*")
        print("The path selected is: {}".format(opened_path))
        self.ui.QGDML.setText(opened_path)
        # Read parameters from csv file
        self.duration, self.freq_list, self.power_list, self.error, self.msg  = rcsv.read_and_plot(opened_path, self.ui.Qenable_plot.isChecked(), False)
        self.ui.QoutputLabel.setText(self.msg)
        if not self.error:
            self.enablePlayButton()


    def play_execution(self):
        self.disablePlayButton()
        self.enableStopButton()
        self.enablePauseButton()
        self.run_long_task()


    def pause_execution(self):
        #define pause
        return


    def stop_execution(self):
        self.worker.stop_execution()
        # self.execution = False


    def update_values_on_screen(self, msg):
        _translate = QtCore.QCoreApplication.translate
        self.ui.Qtemperature_label.setText(_translate("MainWindow", str(msg.Temperature)))
        self.ui.Qpll_label.setText(_translate("MainWindow", str(msg.PLL)))
        self.ui.Qcurrent_label.setText(_translate("MainWindow", str(msg.Current)))
        self.ui.Qvoltage_label.setText(_translate("MainWindow", str(msg.Voltage)))
        self.ui.Qreflectedpower_label.setText(_translate("MainWindow", str(msg.Reflected_Power)))
        self.ui.Qforwardpower_label.setText(_translate("MainWindow", str(msg.Forward_Power)))
        self.ui.Qpwm_label.setText(_translate("MainWindow", str(msg.PWM)))
        self.ui.Qonoff_label.setText(_translate("MainWindow", str(msg.On_Off)))
        self.ui.Qenablefoldback_label.setText(_translate("MainWindow", str(msg.Enable_foldback)))
        self.ui.Qfoldbackin_label.setText(_translate("MainWindow", str(msg.Foldback_in)))
        self.ui.Qerror_label.setText(_translate("MainWindow", str(msg.Error)))


    def enablePlayButton(self):
        self.ui.Qplay.setEnabled(True)

    def disablePlayButton(self):
        self.ui.Qplay.setEnabled(False)

    def enablePauseButton(self):
        self.ui.Qpause.setEnabled(True)

    def disablePauseButton(self):
        self.ui.Qpause.setEnabled(False)

    def enableStopButton(self):
        self.ui.Qstop.setEnabled(True)

    def disableStopButton(self):
        self.ui.Qstop.setEnabled(False)

    def close(self):
        # self.close()
        QApplication.quit()


def update_status(msg):
    window.update_values_on_screen(msg)


def update_progress(progress_bar, value):
    progress_bar.setValue(value)

    if value >= 100:
        progress_bar.setVisible(False)
    elif progress_bar.isHidden():
        progress_bar.setVisible(True)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())