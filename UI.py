from PyQt5 import QtCore # QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow #QWidget, QInputDialog, QLineEdit
import time
import datetime
import read_csv as rcsv
import serial_RW as srw
from UI_raw import Ui_MainWindow
import sys
# from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThreadPool
from PyQt5.QtCore import pyqtSignal # QThread
import plc_communication as plcc

from threading import Thread

# Set the COM port

def read_config(filename):
    csv_name = ""

    with open(filename, 'r') as file:
        lines = file.readlines()

    com = "COM"+str(lines[0])
    if len(lines) >= 2:
        csv_name = str(lines[1])
    return com, csv_name

comport, csv_name = read_config("config.txt")
plc_thread_exec = True # used to stop the plc reading thread
plc_status = 0
is_plot_present = False # tells if the csv plot is already present and therefore will be overwritten by another csv

class RFdata:
    Temperature = "--"
    PLL = "--"
    Current = "--"
    Voltage = "--"
    Reflected_Power = "--"
    Forward_Power= "--"
    PWM = "--"
    On_Off = "--"
    Enable_foldback = "--"
    Foldback_in = "--"
    Error = "--"
    cycle_count = 0
    cycle_percentage = 0

# File di log
log_file = "log.txt"

def write_to_file(filename, text):
    try:
        with open(filename, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    content = text + "\n" + content
    with open(filename, "w") as f:
        f.write(content)
    f.close()

rf_data = RFdata()
index = 0
interruption_type = "" # "stop", "reset"
num_executed_cycles = 1
execution_time = 0
prev_execution_time = 0
threshold_stop = False
thres_status = ""


class PLCWorker(QtCore.QObject):
    execution = False
    messaged = pyqtSignal()
    finished = pyqtSignal()

    def stop_worker_execution(self):
        if self.execution:
            self.execution = False
        else:
            print("Execution stopped.")

    def start_execution(self):
        print("Started execution")
        self.execution = True

    def run(self):
        global plc_status
        global plc_thread_exec

        print("In run for plc communication...")
        self.start_execution()

        while plc_thread_exec:
            plc_status = 1 # plcc.is_plc_on_air()  #TODO set to 1 for testing purposes
            time.sleep(0.5)
            self.messaged.emit()
            # print(plc_status)
            # self.messaged.emit()

        print("plc communication finished")
        self.messaged.emit()
        self.finished.emit()


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

    safe_mode_param = 1 # base value 1, in safe mode 2/3
    threshold_security_mode = False
    starttime_security_mode = 0
    duration_security_mode = 30 # seconds
    safety_mode_counter = 0
    force_change_pwr_safety = False

    noresp_counter = 0

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


    def check_thresholds(self, rf_data):
        '''Check the thresholds and return a bool'''
        global thres_status

        thres_exceeded = False
        if rf_data.Temperature != "--" and rf_data.Voltage != "--" and rf_data.Current != "--" and rf_data.Reflected_Power != "--" and rf_data.Forward_Power != "--":
            if int(rf_data.Temperature) >= 65 or int(rf_data.Voltage) >= 33 or int(rf_data.Current) >= 18 or int(rf_data.Reflected_Power) >= 150 or int(rf_data.Forward_Power) >= 260:
                thres_status = "Threshold Err. Temp {}C, Volt {}V, Curr {}A, R.Pow {}W, Pow {}W".format(rf_data.Temperature,rf_data.Voltage,rf_data.Current,rf_data.Reflected_Power,rf_data.Forward_Power)
                thres_exceeded = True
        return thres_exceeded


    def safe_mode(self, rf_data):
        global threshold_stop
        global thres_status
        '''Change the state of the system based on the thresholds.'''

        if not self.threshold_security_mode:
            if self.check_thresholds(rf_data):
                print("Entering SAFE MODE, status: {}".format(thres_status))
                self.threshold_security_mode = True

        if self.threshold_security_mode: # not else because otherwise it skips the first
            if self.starttime_security_mode == 0:
                self.safe_mode_param = 2/3
                self.starttime_security_mode = time.time()
                self.force_change_pwr_safety = True # force the change of pwr
            else:
                if time.time() >= self.starttime_security_mode + self.duration_security_mode:
                    if self.check_thresholds(rf_data):
                        self.starttime_security_mode = time.time()
                        # try to gradually reduce the output power. After N times, the system is stopped (equivalent to a Reset).
                        self.safety_mode_counter += 1
                        self.safe_mode_param = (2-0.5*self.safety_mode_counter)/3
                        self.force_change_pwr_safety = True # force the change of pwr
                        print("Reduced value to {}".format(self.safe_mode_param))
                        if self.safety_mode_counter >= 3:
                            print("Stopping: unsafe parameters.")
                            threshold_stop = True
                    else:
                        print("Exiting from Safe Mode.")
                        self.safe_mode_param = 1
                        self.safety_mode_counter = 0
                        self.threshold_security_mode = False
                        self.starttime_security_mode = 0
                        self.force_change_pwr_safety = True

    def run(self):
        global rf_data
        global comport
        global index
        global num_executed_cycles
        global execution_time
        global prev_execution_time
        global interruption_type
        global threshold_alarm
        global thres_status
        global plc_status
        global log_file

        if interruption_type == "reset":
            prev_execution_time = 0

        print("In run...")
        self.start_execution()

        print("Opening connection with RF...")
        ser = srw.connect_serial(comport)

        # reset parameters for the safe mode (useful when stopping while in the safe mode)
        self.safe_mode_param = 1
        self.safety_mode_counter = 0
        self.threshold_security_mode = False
        self.starttime_security_mode = 0

        next_time = self.duration[0]
        freq = self.freq_list[0]
        power = self.power_list[0]

        srw.send_cmd_string(ser,"ON")

        srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
        srw.empty_buffer(ser, wait=1)
        srw.send_cmd_string(ser,"FLDBCK_ON", redundancy=3)
        srw.empty_buffer(ser, wait=0.5)
        srw.send_cmd_string(ser,"FLDBCK_VAL", 5, redundancy=3)
        srw.empty_buffer(ser, wait=0.5)
        srw.send_cmd_string(ser,"FREQ", freq, redundancy=1)

        rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)
        time.sleep(0.2)

        # Start the main functions
        timestamp = time.time()
        starttime = time.time()
        min_refresh = 1
        cycle_time = time.time()

        while self.execution and threshold_stop == False and plc_status:
            if time.time() >= timestamp + min_refresh: # minimum refresh period

                if self.noresp_counter >= 30:
                    print("Exit because of: No Response from serial!")
                    date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                    write_to_file(log_file, "{} {}".format(date_time, "stopped execution: no response from serial"))
                    self.execution = False
                    rf_data.On_Off = 0
                # print("Il plc al momento vale: {}".format(plc_status))
                self.safe_mode(rf_data)
                if self.force_change_pwr_safety:
                    srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
                    self.force_change_pwr_safety = False

                if time.time()-cycle_time >= next_time:

                    index += 1
                    index = index % len(self.duration)  # set to 0 if is the last line in the csv

                    next_time = next_time + self.duration[index]
                    power = self.power_list[index]
                    freq = self.freq_list[index]
                    if index == 0:
                        num_executed_cycles += 1
                        cycle_time = time.time()
                        next_time = self.duration[index]

                    srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
                    srw.send_cmd_string(ser,"FREQ", freq, redundancy=3)


                rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)
                rf_data.cycle_count = num_executed_cycles
                rf_data.cycle_percentage = round(index/(len(self.duration))*100, 0)
                self.messaged.emit()
                timestamp = time.time()
                execution_time = prev_execution_time + (timestamp - starttime)
                if rf_data.Error == 4:   #tentativo
                    print("Re-set parameters")
                    srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param)
                    srw.send_cmd_string(ser,"FREQ", freq)
                if rf_data.Error == 203:   #writing not enabled (probably off?)
                    print("Restart")
                    # restart the rf

                    check = False
                    while check == False:
                        srw.send_cmd_string(ser,"ON")
                        print("Setting pwr {}".format(power))
                        rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)
                        time.sleep(1)
                        if rf_data.On_Off == 1:
                            srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
                            srw.send_cmd_string(ser,"FREQ", freq, redundancy=3)
                            check = True
                            rf_data.Error = 0

        # Soft turn off
        print("\nShutting down...")
        srw.send_cmd_string(ser,"PWM", 0, 2)
        srw.send_cmd_string(ser,"OFF")
        srw.empty_buffer(ser, wait=1)

        prev_execution_time = execution_time
        rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)

        rf_data.Temperature = "--"
        rf_data.PLL = "--"
        rf_data.Current = "--"
        rf_data.PWM = "--"
        rf_data.Foldback_in = "--"
        rf_data.Enable_foldback = "--"
        rf_data.Error = "--"
        rf_data.Voltage = "--"

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
    plcworker = None
    thread = None
    thread_plc = None

    last_status_update = 0


    def __init__(self):

        global csv_name

        global is_plot_present

        self.__thread = QtCore.QThread()
        self.__thread_plc = QtCore.QThread()

        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.QOpen_CSV.clicked.connect(lambda: self.open_file("Open_CSV"))
        self.ui.Qexit.clicked.connect(lambda: self.close())

        self.ui.Qplay.clicked.connect(lambda: self.play_execution())

        self.ui.Qstop.clicked.connect(lambda: self.stop_execution())
        self.ui.Qreset.clicked.connect(lambda: self.reset_execution())

        self.run_plc_check()


        self.duration, self.freq_list, self.power_list, self.error, self.msg  = rcsv.read_and_plot(self.ui, csv_name, is_plot_present)
        if not self.error:
            self.ui.Qcsvpath.setText(csv_name)
            is_plot_present = True
            self.enablePlayButton()
            self.ui.QoutputLabel.setText(self.msg)


    def run_plc_check(self):
        if not self.__thread_plc.isRunning():
            self.__thread_plc = self.__get_thread_plc()
            self.__thread_plc.start()
        else:
            print("Thread already running, killing it")
            # print("thread id is {}".format(int(self.__thread_plc.currentThreadId())))
            self.__thread_plc.quit()
            time.sleep(3)
            self.__thread_plc = self.__get_thread_plc()
            self.__thread_plc.start()
            # print("thread id is {}".format(int(self.__thread_plc.currentThreadId())))


    def run_long_task(self):
        if not self.__thread.isRunning():
            self.__thread = self.__get_thread()
            self.__thread.start()
            # print("first iteration, thread id is {}".format(int(self.__thread.currentThreadId())))
        else:
            print("Thread already running, killing it")
            # print("thread id is {}".format(int(self.__thread.currentThreadId())))
            self.__thread.quit()
            time.sleep(3)
            self.__thread = self.__get_thread()
            self.__thread.start()
            # print("thread id is {}".format(int(self.__thread.currentThreadId())))


    def __get_thread_plc(self):
        self.thread_plc = QtCore.QThread()
        self.plcworker = PLCWorker()
        self.plcworker.moveToThread(self.thread_plc)

        self.thread_plc.plcworker = self.plcworker

        self.thread_plc.started.connect(self.plcworker.run)
        self.plcworker.finished.connect(lambda: self.quit_thread_plc())
        self.plcworker.messaged.connect(lambda: self.update_plc_status())

        return self.thread_plc

    def __get_thread(self):
        self.thread = QtCore.QThread()
        self.worker = Worker()
        self.worker.give_values(self.duration, self.freq_list, self.power_list)
        self.worker.moveToThread(self.thread)

        # this is essential when worker is in local scope!
        self.thread.worker =  self.worker

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(lambda: self.quit_thread())

        # worker.progressed.connect(lambda value: update_progress(self.ui.progressBar, value))   #for a progress bar
        # worker.messaged.connect(lambda msg: update_status(self.statusBar(), msg))
        self.worker.messaged.connect(lambda: self.update_status())
        return self.thread

    def quit_thread(self):
        global interruption_type
        self.thread.quit

    def quit_thread_plc(self):
        global plc_thread_exec
        plc_thread_exec = False
        self.thread_plc.quit

    def restore_buttons(self):
        self.enablePlayButton()
        if interruption_type == "stop":
            self.disableStopButton()
            self.ui.QoutputLabel.setText("Process stopped.")
        elif interruption_type == "reset":
            self.disableResetButton()
            self.disableStopButton()
            self.enableOpenCSVButton()
            self.enableExitButton()
            self.ui.QoutputLabel.setText("Process ended.")

    scheme = "LAST_CYCLE_STATUS"

    def status_log_file(self, filename, updated_line):
        update = False
        with open(filename, 'r') as f:
            lines = f.readlines()

        if "play" in lines[0]:
            lines[0] = self.scheme + " " + updated_line + "\n" + lines[0]
            update = True
        elif self.scheme in lines[0]:
            lines[0] = self.scheme + " " + updated_line + "\n"
            update = True
        # else:
            # print("Not in PLAY mode")


        # Write the updated contents back to the file
        if update:
            with open(filename, 'w') as f:
                f.writelines(lines)

    def save_error_log(self):
        to_add = False
        if self.rf_values.Error != "No error":
            if len(self.error_history) != 0:
                if self.error_history[-1][1] != self.rf_values.Error:
                    to_add = True
                elif time.time()-self.error_history[-1][0] >= 60:
                    # print("Add with {} seconds!".format(time.time()-self.error_history[-1][0]))
                    to_add = True
            else:
                # print("Add: first elem")
                to_add = True
            if to_add:
                self.error_history.append([time.time(), self.rf_values.Error])
        self.rf_values.Error = "No error"

    def open_file(self, button_name):
        global csv_name
        global is_plot_present
        # Reads the file path from the prompt
        self.disablePlayButton()
        file_type = button_name.split("_")[1]
        path = ""

        opened_path, _ = QFileDialog.getOpenFileName(None, "Open the {} file".format(file_type), path, "*")
        # Read parameters from csv file
        if opened_path != "":
            self.ui.Qcsvpath.setText(opened_path)
            self.duration, self.freq_list, self.power_list, self.error, self.msg  = rcsv.read_and_plot(self.ui, opened_path, is_plot_present)
            self.ui.QoutputLabel.setText(self.msg)
            if not self.error:
                is_plot_present = True
                self.enablePlayButton()

    def play_execution(self):
        global log_file
        self.ui.QoutputLabel.setText("Process started.")
        # Save log file
        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        write_to_file(log_file, "{} {}".format(date_time, "Software ON, ready to start."))
        self.disablePlayButton()
        self.enableStopButton()
        self.enableResetButton()
        self.disableExitButton()
        self.disableOpenCSVButton()
        self.run_long_task()

    def reset_execution(self):
        global index
        global interruption_type
        global num_executed_cycles
        interruption_type = "reset"
        num_executed_cycles = 1
        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        write_to_file(log_file, "{} {}".format(date_time, "reset"))
        write_to_file(log_file, "{}".format("--"))
        self.ui.QoutputLabel.setText("Process reset.")
        self.worker.stop_worker_execution()
        index = 0
        self.restore_buttons()

    def stop_execution(self):
        global interruption_type
        interruption_type = "stop"
        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        write_to_file(log_file, "{} {}".format(date_time, "stop"))
        self.ui.QoutputLabel.setText("Process stopped.")
        self.worker.stop_worker_execution()
        self.restore_buttons()


    def enablePlayButton(self):
        self.ui.Qplay.setEnabled(True)

    def disablePlayButton(self):
        self.ui.Qplay.setEnabled(False)

    def enableStopButton(self):
        self.ui.Qstop.setEnabled(True)

    def disableStopButton(self):
        self.ui.Qstop.setEnabled(False)

    def enableResetButton(self):
        self.ui.Qreset.setEnabled(True)

    def disableResetButton(self):
        self.ui.Qreset.setEnabled(False)

    def enableExitButton(self):
        self.ui.Qexit.setEnabled(True)

    def disableExitButton(self):
        self.ui.Qexit.setEnabled(False)

    def enableOpenCSVButton(self):
        self.ui.QOpen_CSV.setEnabled(True)

    def disableOpenCSVButton(self):
        self.ui.QOpen_CSV.setEnabled(False)

    def close(self):
        global plc_thread_exec
        if self.thread:
            self.thread.quit
        if self.thread_plc:
            plc_thread_exec = False
            self.thread_plc.quit
        QApplication.quit()

    def update_status(self):
        global rf_data
        global execution_time
        global threshold_stop
        global thres_status
        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

        _translate = QtCore.QCoreApplication.translate
        self.ui.Qtemperature_label.setText(_translate("MainWindow", str(rf_data.Temperature)+" °C"))
        self.ui.Qpll_label.setText(_translate("MainWindow", str(rf_data.PLL)))
        self.ui.Qcurrent_label.setText(_translate("MainWindow", str(rf_data.Current))+" A")
        self.ui.Qvoltage_label.setText(_translate("MainWindow", str(rf_data.Voltage))+" V")
        self.ui.Qreflectedpower_label.setText(_translate("MainWindow", str(rf_data.Reflected_Power)+" W"))
        self.ui.Qforwardpower_label.setText(_translate("MainWindow", str(rf_data.Forward_Power)+" W"))
        self.ui.Qpwm_label.setText(_translate("MainWindow", str(rf_data.PWM)))
        if str(rf_data.On_Off) == "1":
            self.ui.Qonoff_label.setText(_translate("MainWindow", "On"))
            self.ui.Qonoff_label.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(85, 255, 0);")
        else:
            self.ui.Qonoff_label.setText(_translate("MainWindow", "Off"))
            self.ui.Qonoff_label.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(255, 0, 0);")

        if threshold_stop:
            self.ui.QoutputLabel.setText("THRESHOLD ALARM, see log file.")
            write_to_file(log_file, "{} {}".format(date_time, thres_status))
            threshold_stop = False

        self.ui.Qenablefoldback_label.setText(_translate("MainWindow", str(rf_data.Enable_foldback)))
        self.ui.Qfoldbackin_label.setText(_translate("MainWindow", str(rf_data.Foldback_in)+" W"))
        self.ui.Qerror_label.setText(_translate("MainWindow", str(rf_data.Error)))
        self.ui.Qcyclenumber.setText(_translate("MainWindow", str(rf_data.cycle_count)))
        self.ui.Qcurrentcycle.setText(_translate("MainWindow", str(rf_data.cycle_percentage)))
        self.ui.Qexecution_time.setText(_translate("MainWindow", str(datetime.timedelta(seconds = int(execution_time)))))

        if time.time() > self.last_status_update + 60:
            self.status_log_file(log_file, "{} - cycle num: {} - cycle progress: {}%".format(date_time, rf_data.cycle_count, rf_data.cycle_percentage))
            self.last_status_update = time.time()

    def update_plc_status(self):
        global plc_status
        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

        if plc_status:
            # print("Update with green color")
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(85, 255, 0);")
        else:
            # print("Update with red color")
            # self.ui.Qonoff_label.setText(_translate("MainWindow", "Off"))
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(255, 0, 0);")
            write_to_file(log_file, "{} {}".format(date_time, "stop from PLC"))

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