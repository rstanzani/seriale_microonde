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

def read_config(filename):
    csv_name = ""
    with open(filename, 'r') as file:
        lines = file.readlines()
    com = "COM"+str(lines[0][0])
    if len(lines) >= 2:
        csv_name = str(lines[1])
    return com, csv_name

# import time
# inizio = time.time()

#TODO list:
# (001) - re-enable plc_status check
# (002) - remove plc_status hardcoded to 1
# (003) - re-enable autostart after

comport, csv_name = read_config("config.txt")
plc_thread_exec = True # used to stop the plc reading thread
plc_status = 0
old_plc_status = 0
is_plot_present = False # tells if the csv plot is already present and therefore will be overwritten by another csv

duration = 0
freq_list = []
power_list = []

freq = 0

turn_on = True
just_turned_off = True   #when the user click STOP or RESET buttons

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
interruption_type = "reset" # "stop", "reset", default value reset
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
        print("Started execution in PLCworker")
        self.execution = True


    def run(self):
        global plc_status
        global plc_thread_exec
        global inizio

        print("In run for plc communication...")
        self.start_execution()

        while plc_thread_exec:
            # controllo = time.time() - inizio
            plc_status = plcc.is_plc_on_air()  #TODO set to 1 for testing purposes
            # if controllo > 30 and controllo < 60:
            #     plc_status = 0 # plcc.is_plc_on_air()  #TODO (002)
            time.sleep(0.5)
            self.messaged.emit()

        print("plc communication finished")
        self.messaged.emit()
        self.finished.emit()


class Worker(QtCore.QObject):
    execution = False
    messaged = pyqtSignal()
    finished = pyqtSignal()
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
        print("Started execution in Worker")
        self.execution = True


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
        global old_plc_status
        global log_file

        global duration
        global freq_list
        global freq
        global power_list

        global turn_on
        global just_turned_off

        print("In run...")
        self.start_execution()

        self.safe_mode_param = 1
        self.safety_mode_counter = 0
        self.threshold_security_mode = False
        self.starttime_security_mode = 0

        print("Opening connection with RF...")
        ser = srw.connect_serial(comport)
        while plc_thread_exec:

            # ACTIVE STATUS
            if self.execution and not threshold_stop: # and plc_status:   #TODO (001)

                if turn_on: # to turn on only in the first iteration

                    if interruption_type == "reset":
                        if isinstance(duration, list):
                            next_time = duration[0]
                            freq = freq_list[0]
                            power = power_list[0]
                        prev_execution_time = 0

                    srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
                    srw.empty_buffer(ser, wait=1)
                    srw.send_cmd_string(ser,"FLDBCK_ON", redundancy=3)
                    srw.empty_buffer(ser, wait=0.5)
                    srw.send_cmd_string(ser,"FLDBCK_VAL", 5, redundancy=3)
                    srw.empty_buffer(ser, wait=0.5)
                    srw.send_cmd_string(ser,"FREQ", freq, redundancy=1)

                    date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                    write_to_file(log_file, "{} {}".format(date_time, "RF on"))

                    rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)
                    time.sleep(0.2)

                    # Start the main functions
                    timestamp = time.time()
                    starttime = time.time()
                    min_refresh = 1
                    cycle_time = time.time()
                    turn_on = False
                    just_turned_off = True

                if time.time() >= timestamp + min_refresh: # minimum refresh period

                    if self.noresp_counter >= 30:
                        print("Exit: no Response from serial!")
                        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                        write_to_file(log_file, "{} {}".format(date_time, "stopped execution: no response from serial"))
                        self.execution = False
                        rf_data.On_Off = 0

                    self.safe_mode(rf_data)
                    if self.force_change_pwr_safety:
                        srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
                        self.force_change_pwr_safety = False

                    if time.time()-cycle_time >= next_time:

                        index += 1
                        index = index % len(duration)  # set to 0 if is the last line in the csv

                        next_time = next_time + duration[index]
                        power = power_list[index]
                        freq = freq_list[index]
                        if index == 0:
                            num_executed_cycles += 1
                            cycle_time = time.time()
                            next_time = duration[index]

                        srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
                        srw.send_cmd_string(ser,"FREQ", freq, redundancy=3)

                    rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)
                    rf_data.cycle_count = num_executed_cycles
                    rf_data.cycle_percentage = round(index/(len(duration))*100, 0)
                    self.messaged.emit()
                    timestamp = time.time()
                    execution_time = prev_execution_time + (timestamp - starttime)
                    if rf_data.Error == 4:   #tentativo
                        print("Re-set parameters")
                        srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param)
                        srw.send_cmd_string(ser,"FREQ", freq)
                    if rf_data.Error == 203:   #writing not enabled (probably off?)
                        print("Restart")

                        check = False
                        while check == False:
                            srw.send_cmd_string(ser,"ON")
                            rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)
                            time.sleep(1)
                            if rf_data.On_Off == 1:
                                srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
                                srw.send_cmd_string(ser,"FREQ", freq, redundancy=3)
                                check = True
                                rf_data.Error = 0
            elif just_turned_off:
                print("\nShutting down...")
                # if plc_status == 0:     # TODO (001)
                #     interruption_type = "stop"

                srw.send_cmd_string(ser,"PWM", 0, 2)
                srw.send_cmd_string(ser,"OFF")
                srw.empty_buffer(ser, wait=1)

                prev_execution_time = execution_time
                rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)

                turn_on = True
                just_turned_off = False

            # IDLE STATUS
            else:
                if time.time() >= timestamp + min_refresh:
                    rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)
                    self.messaged.emit()

            # check plc variation
            if old_plc_status != plc_status:
                print("PLC status changes")
                date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                if plc_status:
                    write_to_file(log_file, "{} {}".format(date_time, "PLC status ON."))
                else:
                    write_to_file(log_file, "{} {}".format(date_time, "PLC status OFF."))
            old_plc_status = plc_status

        # Soft turn off
        print("Main thread killed by the user, shut down and close serial")
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
        global duration
        global freq_list
        global power_list

        self.__thread = QtCore.QThread()
        self.__thread_plc = QtCore.QThread()

        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.QOpen_CSV.clicked.connect(lambda: self.open_file("Open_CSV"))
        self.ui.Qexit.clicked.connect(lambda: self.close())

        self.run_plc_check()

        # read from csv
        duration, freq_list, power_list, self.error, self.msg  = rcsv.read_and_plot(self.ui, csv_name, is_plot_present)
        if not self.error:
            self.ui.Qcsvpath.setText(csv_name)
            is_plot_present = True
            self.enablePlayButton()
            self.ui.QoutputLabel.setText(self.msg)

        self.open_window_init()    # init the functionalities when opening the program
        self.ui.Qplay.clicked.connect(lambda: self.play_execution())
        self.ui.Qstop.clicked.connect(lambda: self.stop_execution())
        self.ui.Qreset.clicked.connect(lambda: self.reset_execution())


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


    def run_long_task(self):
        if not self.__thread.isRunning():
            self.__thread = self.__get_thread()
            self.__thread.start()
            # print("thread id: {}".format(int(self.__thread.currentThreadId())))
        else:
            print("Thread already running, killing it")
            self.__thread.quit()
            time.sleep(3)
            self.__thread = self.__get_thread()
            self.__thread.start()


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
        self.worker.moveToThread(self.thread)

        # this is essential when worker is in local scope!
        self.thread.worker =  self.worker

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(lambda: self.quit_thread())

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


    def status_log_file(self, filename, updated_line):
        update = False
        with open(filename, 'r') as f:
            lines = f.readlines()

        if "RF on" in lines[0]:
            lines[0] = "LAST_CYCLE_STATUS" + " " + updated_line + "\n" + lines[0]
            update = True
        elif "LAST_CYCLE_STATUS" in lines[0]:
            lines[0] = "LAST_CYCLE_STATUS" + " " + updated_line + "\n"
            update = True

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
                    to_add = True
            else:
                to_add = True
            if to_add:
                self.error_history.append([time.time(), self.rf_values.Error])
        self.rf_values.Error = "No error"


    def open_file(self, button_name):
        global csv_name
        global is_plot_present
        global duration
        global freq_list
        global power_list

        # Reads the file path from the prompt
        self.disablePlayButton()
        file_type = button_name.split("_")[1]
        path = ""

        opened_path, _ = QFileDialog.getOpenFileName(None, "Open the {} file".format(file_type), path, "*")
        # Read parameters from csv file
        if opened_path != "":
            self.ui.Qcsvpath.setText(opened_path)
            duration, freq_list, power_list, self.error, self.msg  = rcsv.read_and_plot(self.ui, opened_path, is_plot_present)

            self.ui.QoutputLabel.setText(self.msg)
            if not self.error:
                is_plot_present = True
                self.enablePlayButton()


    def open_window_init(self):
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


    def play_execution(self):
        global log_file
        global modifica_alf   # TODO (003): remove this 

        modifica_alf = True    # TODO (003): remove this 

        self.disablePlayButton()
        self.enableStopButton()
        self.enableResetButton()
        self.disableExitButton()
        self.disableOpenCSVButton()
        self.worker.start_execution()


    def reset_execution(self):
        global index
        global interruption_type
        global num_executed_cycles
        interruption_type = "reset"
        num_executed_cycles = 1
        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        write_to_file(log_file, "{} {}".format(date_time, "Reset"))
        self.ui.QoutputLabel.setText("Process reset.")
        self.worker.stop_worker_execution()
        index = 0
        self.restore_buttons()


    def stop_execution(self):
        global interruption_type
        interruption_type = "stop"
        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        write_to_file(log_file, "{} {}".format(date_time, "Stop"))
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
        global log_file

        if self.thread:
            self.thread.quit
        if self.thread_plc:
            plc_thread_exec = False
            self.thread_plc.quit
        time.sleep(3)

        write_to_file(log_file, "{}".format("--"))
        print("Window closing...")
        QApplication.quit()


    def update_status(self):
        global rf_data
        global execution_time
        global threshold_stop
        global thres_status
        global interruption_type
        global freq
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
            interruption_type = "reset"

        self.ui.Qfrequency.setText(_translate("MainWindow", str(freq)))

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
        global modifica_alf    # TODO (003): remove this 
        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

        if plc_status:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(85, 255, 0);")
        else:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(255, 0, 0);")
            if modifica_alf:  # TODO (003): remove this 
                # self.reset_execution()
                modifica_alf = False


modifica_alf = True # TODO (003): remove this 

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