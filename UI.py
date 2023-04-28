from PyQt5 import QtCore # QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow #QWidget, QInputDialog, QLineEdit
import time
import read_csv as rcsv
import serial_RW as srw
from UI_raw import Ui_MainWindow
import sys
from PyQt5.QtCore import pyqtSignal # QThread
import search_serials as ssr

# https://realpython.com/python-pyqt-qthread/
# https://www.xingyulei.com/post/qt-threading/
# TODO: rimuovere l'uso del dict per i campi
comport = "COM9"

class RFdata:
    Temperature = "N.D."
    PLL = "N.D."
    Current = "N.D."
    Voltage = "N.D."
    Reflected_Power = "N.D."
    Forward_Power= "N.D."
    PWM = "N.D."
    On_Off = "N.D."
    Enable_foldback = "N.D."
    Foldback_in = "N.D."
    Error = "N.D."

    def set_values(self, temp, pll, curr, vol, refl, frw, pwm, onoff, ena, fld, err):
        self.Temperature = temp
        self.PLL = pll
        self.Current = curr
        self.Voltage = vol
        self.Reflected_Power = refl
        self.Forward_Power = frw
        self.PWM = pwm
        self.On_Off = onoff
        self.Enable_foldback = ena
        self.Foldback_in = fld
        self.Error = err

rf_data = RFdata()
index = 0
interruption_type = "" # "pause", "stop"

class Worker(QtCore.QObject):

    execution = False
    duration = 0
    freq_list = []
    power_list = []
    messaged = pyqtSignal()
    finished = pyqtSignal()
    duration = 0
    freq_list = []
    power_list = []

    def stop_worker_execution(self):
        if self.execution:
            self.execution = False
        else:
            print("Execution stopped.")

    def start_execution(self):
        print("Started execution")
        self.execution = True

    def give_values(self, duration, freq_list, power_list):
        self.duration = duration
        self.freq_list = freq_list
        self.power_list = power_list

    def run(self):
        global rf_data
        global comport
        global index

        print("In run...")
        self.start_execution()
        # global execution
        print("Opening connection with RF...")
        ser = srw.connect_serial(comport)

        next_time = self.duration[0]
        freq = self.freq_list[0]
        power = self.power_list[0]

        srw.send_cmd_string(ser,"ON")
        srw.send_cmd_string(ser,"PWR", power)
        srw.send_cmd_string(ser,"FREQ", freq)
        rf_data = srw.read_param(ser, rf_data, "STATUS", 1, False)

        # Start the main functions
        timestamp = time.time()
        min_refresh = 1
        init_time = time.time()

        while self.execution:
            if time.time() >= timestamp + min_refresh: # minimum refresh period
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
                rf_data = srw.read_param(ser, rf_data, "STATUS", False)
                rf_data = srw.read_param(ser, rf_data, "FLDBCK_READ", False)
                self.messaged.emit()
                timestamp = time.time()

        # Soft turn off
        print("\nShutting down...")
        srw.send_cmd_string(ser,"OFF")
        srw.send_cmd_string(ser,"PWM", 0)
        srw.empty_buffer(ser, wait=1)
        rf_data = srw.read_param(ser, rf_data, "STATUS")

        # Close ports
        ser.close()
        print("COM port correctly closed")
        self.messaged.emit()
        self.finished.emit()


class MainWindow(QMainWindow):
    ui = None
    duration = 0
    freq_list = []
    power_list = []
    error = ""
    msg = ""
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
        self.ui.Qpause.clicked.connect(lambda: self.pause_execution())
        self.ui.Qstop.clicked.connect(lambda: self.stop_execution())
        self.ui.Qsearchserial.clicked.connect(lambda: self.search_serials())


    def run_long_task(self):
        if not self.__thread.isRunning():
            self.__thread = self.__get_thread()
            self.__thread.start()
        else:
            print("Thread already running, killing it")
            self.__thread.quit()
            self.__thread = self.__get_thread()
            self.__thread.start()


    def __get_thread(self):
        self.thread = QtCore.QThread()
        self.worker = Worker()
        self.worker.give_values(self.duration, self.freq_list, self.power_list)
        self.worker.moveToThread(self.thread)

        # this is essential when worker is in local scope!
        self.thread.worker =  self.worker

        self.thread.started.connect( self.worker.run)
        self.worker.finished.connect(lambda: self.quit_thread())

        # worker.progressed.connect(lambda value: update_progress(self.ui.progressBar, value))   #for a progress bar
        # worker.messaged.connect(lambda msg: update_status(self.statusBar(), msg))
        self.worker.messaged.connect(lambda: self.update_status())

        return self.thread


    def quit_thread(self):
        global interruption_type
        self.thread.quit

    def restore_buttons(self):
        self.enablePlayButton()
        if interruption_type == "pause":
            self.disablePauseButton()
            self.ui.QoutputLabel.setText("Process paused.")
        elif interruption_type == "stop":
            self.disableStopButton()
            self.enableSearchSerialButton()
            self.enableOpenCSVButton()
            self.enableExitButton()
            self.ui.QoutputLabel.setText("Process ended.")


    def save_error_log(self):
        to_add = False
        if self.rf_values.Error != "No error":
            if len(self.error_history) != 0:
                if self.error_history[-1][1] != self.rf_values.Error:
                    print("Add: new value")
                    to_add = True
                elif time.time()-self.error_history[-1][0] >= 60:
                    print("Add with {} seconds!".format(time.time()-self.error_history[-1][0]))
                    to_add = True
            else:
                print("Add: first elem")
                to_add = True
            if to_add:
                self.error_history.append([time.time(), self.rf_values.Error])
        self.rf_values.Error = "No error"


    def open_file(self, button_name):
        # Reads the file path from the prompt
        self.disablePlayButton()
        file_type = button_name.split("_")[1]
        path = ""
        opened_path, _ = QFileDialog.getOpenFileName(None, "Open the {} file".format(file_type), path, "*")
        # Read parameters from csv file
        if opened_path != "":
            self.ui.QGDML.setText(opened_path)
            self.duration, self.freq_list, self.power_list, self.error, self.msg  = rcsv.read_and_plot(opened_path, self.ui.Qenable_plot.isChecked(), False)
            self.ui.QoutputLabel.setText(self.msg)
            if not self.error:
                self.enablePlayButton()

    def play_execution(self):
        self.ui.QoutputLabel.setText("Process started.")
        self.disablePlayButton()
        self.enablePauseButton()
        self.enableStopButton()
        self.disableExitButton()
        self.disableSearchSerialButton()
        self.disableOpenCSVButton()
        self.run_long_task()

    def stop_execution(self):
        global index
        global interruption_type
        interruption_type = "stop"
        self.ui.QoutputLabel.setText("Process stopped.")
        self.worker.stop_worker_execution()
        index = 0
        self.restore_buttons()

    def pause_execution(self):
        global interruption_type
        interruption_type = "pause"
        self.ui.QoutputLabel.setText("Process paused.")
        self.worker.stop_worker_execution()
        self.restore_buttons()


    def search_serials(self):
        self.disablePlayButton()
        self.disableExitButton()
        self.disableOpenCSVButton()
        self.disableSearchSerialButton()
        self.ui.QoutputLabel.setText("Search serials, may take up to 1 minute")
        serial_list = ssr.print_serials()
        self.ui.QoutputLabel.setText("Found serials: {}".format(serial_list))
        self.enableExitButton()
        self.enablePlayButton()
        self.enableOpenCSVButton()
        self.enableSearchSerialButton()

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

    def enableExitButton(self):
        self.ui.Qexit.setEnabled(True)

    def disableExitButton(self):
        self.ui.Qexit.setEnabled(False)

    def enableSearchSerialButton(self):
        self.ui.Qsearchserial.setEnabled(True)

    def disableSearchSerialButton(self):
        self.ui.Qsearchserial.setEnabled(False)

    def enableOpenCSVButton(self):
        self.ui.QOpen_CSV.setEnabled(True)

    def disableOpenCSVButton(self):
        self.ui.QOpen_CSV.setEnabled(False)

    def close(self):
        QApplication.quit()

    def update_status(self):
        global rf_data

        _translate = QtCore.QCoreApplication.translate
        self.ui.Qtemperature_label.setText(_translate("MainWindow", str(rf_data.Temperature)))
        self.ui.Qpll_label.setText(_translate("MainWindow", str(rf_data.PLL)))
        self.ui.Qcurrent_label.setText(_translate("MainWindow", str(rf_data.Current)))
        self.ui.Qvoltage_label.setText(_translate("MainWindow", str(rf_data.Voltage)))
        self.ui.Qreflectedpower_label.setText(_translate("MainWindow", str(rf_data.Reflected_Power)))
        self.ui.Qforwardpower_label.setText(_translate("MainWindow", str(rf_data.Forward_Power)))
        self.ui.Qpwm_label.setText(_translate("MainWindow", str(rf_data.PWM)))
        self.ui.Qonoff_label.setText(_translate("MainWindow", str(rf_data.On_Off)))
        self.ui.Qenablefoldback_label.setText(_translate("MainWindow", str(rf_data.Enable_foldback)))
        self.ui.Qfoldbackin_label.setText(_translate("MainWindow", str(rf_data.Foldback_in)))
        self.ui.Qerror_label.setText(_translate("MainWindow", str(rf_data.Error)))


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