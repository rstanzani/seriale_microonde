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
import os

from threading import Thread

def read_config(filename="config.csv"):
    csv_name = ""
    with open(filename, 'r') as file:
        line = file.readline()
    file.close()
    elem = line.split(";")
    com = "COM"+str(elem[0])
    if len(elem) >= 2:
        csv_name = str(elem[1])
        execution_from_config = 1 if str(elem[2])=="1" else 0

        # Analyzing the filename...
        if csv_name[-7:] == ".rf.csv": # not existant csv
            if not os.path.isfile(csv_name):
                print("ERROR: missing file, please check the file name.")
                execution_from_config = 0
        else:  #invalid csv
            execution_from_config = 0
    return com, csv_name, execution_from_config

#TODO list:

# File di log
log_file = "log.txt"
logger = r"C:\Users\admin\Documents\LOG\logger_EATON.csv"
config_file = "config.csv"

comport, csv_name, execution_from_config = read_config(config_file)
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
min_refresh = 1  # minimum refresh rate

cell_data = plcc.Cell_Data()

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

    def reset(self):
        self.Temperature = "--"
        self.PLL = "--"
        self.Current = "--"
        self.Voltage = "--"
        self.Reflected_Power = "--"
        self.Forward_Power= "--"
        self.PWM = "--"
        self.On_Off = "--"
        self.Enable_foldback = "--"
        self.Foldback_in = "--"
        self.Error = "--"
        self.cycle_count = 0
        self.cycle_percentage = 0


def set_configfile_exec(path, state):
    '''Change the execution status in the config file (used for the next startup)'''
    with open(path, 'r') as file:
        line = file.readline()
    file.close()
    elem = line.split(";")
    if len(elem) >=3:
        elem[2] = state
    lines = ""
    for i in range(0, 3):
        lines += elem[i] + ";"
    with open(path, 'w') as file:
        file.writelines(lines)
    print("Config file execution set to {}".format(state))


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

def write_to_logger(filename, line):

    if os.path.isfile(filename):
        print("File exists")
    else:
        f = open(filename, "w")
        f.write("data;MB11;MB13;;MB110;MB120;MB130;MB150;;MB70;MB80;MB140;MB160;;MW20;MW22;;MW24;MW26;;MW28;MW30;" + "\n") #name of the PLC values
        f.write("data;SP_TAria;SP_TAcqua;;T_Comp1;T_Comp2;T_AriaRF;T_AriaNORF;;T_Bollitore;T_Basale;T_TerraRF;T_TerraNORF;;h_MotoComp;min_MotoComp;;h_SP_Raggiunto;min_SP_Raggiunto;;h_ScaldON;min_ScaldON;" + "\n")
        print("Logger file created: {}".format(filename))
        f.close()

    f = open(filename, "a")
    f.write(line + "\n")
    f.close()

rf_data = RFdata()
index = 0
interruption_type = "reset" # "stop" or "reset" (default value)
num_executed_cycles = 1
execution_time = 0
prev_execution_time = 0
threshold_stop = False
thres_status = ""

prev_logging_time_SHORT = 0
prev_logging_time_LONG = 0
logging_period_LONG = 15 #minutes
logging_period_SHORT = 10 #seconds

execution = False

class PLCWorker(QtCore.QObject):
    # execution = False
    messaged = pyqtSignal()
    finished = pyqtSignal()

    def start_execution(self):
        global execution_from_config
        global execution
        if execution_from_config:
            print("Started execution in PLCworker")
            execution = True
        else:
            print("Execution set to Stop from the config file")

    def run(self):
        global plc_status
        global plc_thread_exec
        # global inizio

        print("In run for plc communication...")
        self.start_execution()

        while plc_thread_exec:
            plc_status = plcc.is_plc_on_air()  #TODO set to 1 for testing purposes
            time.sleep(0.5)
            self.messaged.emit()

        print("plc communication finished")
        self.messaged.emit()
        self.finished.emit()

no_resp_mode = False

class Worker(QtCore.QObject):
    # execution = False
    messaged = pyqtSignal()
    finished = pyqtSignal()
    safe_mode_param = 1 # base value 1, in safe mode 2/3
    threshold_security_mode = False
    starttime_security_mode = 0
    duration_security_mode = 30 # seconds
    safety_mode_counter = 0
    force_change_pwr_safety = False
    noresp_counter = 0
    min_refresh = 1


    def stop_worker_execution(self):
        global execution
        if execution:
            execution = False
        else:
            print("Execution stopped.")


    def start_execution(self):
        global execution
        print("Started execution in Worker")
        execution = True


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
        print("In run...")
        global rf_data
        global comport
        global index
        global num_executed_cycles
        global execution_time
        global execution
        print("*** in run Execution is {}".format(execution))
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
        global prev_logging_time_SHORT
        global prev_logging_time_LONG
        global logging_period_SHORT
        global logging_period_LONG
        global min_refresh

        global no_resp_mode

        self.safe_mode_param = 1
        self.safety_mode_counter = 0
        self.threshold_security_mode = False
        self.starttime_security_mode = 0

        # Initialize timers for PLC logging
        prev_logging_time_SHORT = time.time()
        prev_logging_time_LONG = time.time()
        
        prev_noresp_time = time.time()

        print("Opening connection with RF...")
        ser = srw.connect_serial(comport)

        if isinstance(duration, list):
            remaining_cycle_time = duration[0]

        while plc_thread_exec:

            stopwatch_START = time.time() # START for the stopwatch for the cycle

            if time.time() - prev_logging_time_SHORT >= logging_period_SHORT: # save each 10 s the value from the PLC
                try:
                    read = plcc.get_values()
                    if not read[0]:
                        cell_data.append_values(read[1])
                    else:
                        print("Skipped because data is empty!" )                
                except:
                    print("Error while reading from plc ")
                prev_logging_time_SHORT = time.time()

            if time.time() - prev_logging_time_LONG >= logging_period_LONG*60:  # save to logger and reset the list of values in cell_data
                try:
                    logger_val_str = datetime.datetime.now().strftime("%m/%d/%Y-%H:%M:%S")+";"+plcc.get_logger_values(cell_data)
                    write_to_logger(logger, logger_val_str)
                except:
                    print("Error with PLC reading")
                cell_data.reset()
                prev_logging_time_LONG = time.time()

            if no_resp_mode: # when there is no response from the serial
                if time.time() - prev_noresp_time >= 10:  # each 10 seconds it checks
                    if execution == False and not threshold_stop and plc_status: # restore execution after a stop from serial not responding
                        execution = True
                    prev_noresp_time = time.time()

            # ACTIVE STATUS
            if execution and not threshold_stop and plc_status:

                if turn_on: # to turn on only in the first iteration

                    if interruption_type == "reset":
                        if isinstance(duration, list):
                            remaining_cycle_time = duration[0]
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
                    turn_on = False
                    just_turned_off = True

                if time.time() >= timestamp + min_refresh: # minimum refresh period

                    if self.noresp_counter >= 30:
                        print("Exit: no Response from serial!")
                        if not no_resp_mode:
                            # print("Exit: write on file.")
                            date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                            write_to_file(log_file, "{} {}".format(date_time, "stopped execution: no response from serial"))
                            no_resp_mode = True
                            execution = False
                            rf_data.On_Off = 0
                            rf_data.reset()
                            prev_execution_time = execution_time

                    self.safe_mode(rf_data)
                    if self.force_change_pwr_safety:
                        srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
                        self.force_change_pwr_safety = False

                    if remaining_cycle_time <= 0:    # change the cycle position when the remaining time for this cycle is finished
                        print("Cycle changed!" )
                        index += 1
                        index = index % len(duration)  # set to 0 if is the last line in the csv

                        remaining_cycle_time = duration[index]
                        power = power_list[index]
                        freq = freq_list[index]
                        if index == 0:
                            num_executed_cycles += 1

                        srw.send_cmd_string(ser,"PWR", power*self.safe_mode_param, redundancy=3)
                        srw.send_cmd_string(ser,"FREQ", freq, redundancy=3)

                    rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)
                    # Note: the self.noresp_counter almost never gives perfect 0 due to the various messages that can be lost
                    if no_resp_mode:
                        if self.noresp_counter <= 10:
                            # print("No resp mode reset!")
                            no_resp_mode = False
                            starttime = time.time()  # reset the timer count after a connection restore
                    rf_data.cycle_count = num_executed_cycles
                    rf_data.cycle_percentage = round(index/(len(duration))*100, 0)
                    self.messaged.emit()
                    timestamp = time.time()

                    if not no_resp_mode:
                        execution_time = prev_execution_time + (timestamp - starttime) # calculate the total execution time for the RF generator
                    if rf_data.Error == 4:
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

                srw.send_cmd_string(ser,"PWM", 0, 2)
                srw.send_cmd_string(ser,"OFF")
                srw.empty_buffer(ser, wait=1)

                prev_execution_time = execution_time
                rf_data, self.noresp_counter = srw.read_param(ser, self.noresp_counter, rf_data, "STATUS", 1, False)

                turn_on = True
                just_turned_off = False

            # IDLE STATUS
            else:
                if not 'timestamp' in locals(): # timestamp is not defined if it does not enter in the previous IF (e.g. if pls_status is off when turning on)
                    timestamp = time.time()
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
            stopwatch_STOP = time.time()
            if not no_resp_mode and str(rf_data.On_Off) == "1":
                remaining_cycle_time -= stopwatch_STOP - stopwatch_START # reduce the time only when the RF is working

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
    # execution = True
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
        global execution
        global execution_from_config

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
            if not execution_from_config:
                print("Enable play!")
                self.enablePlayButton()
                self.disableResetButton()
                self.disableStopButton()
                self.enableOpenCSVButton()
                self.enableExitButton()
            else:
                print("Disable play!")
                self.disablePlayButton()
                self.enableResetButton()
                self.enableStopButton()
                self.disableOpenCSVButton()
                self.disableExitButton()
            self.ui.QoutputLabel.setText(self.msg)

        else:
            execution = False
            print("The path is invalid, values of duration, freq_list and others cannot be set.")

		# Disable the X close button
        self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)

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

        if "RF on" in lines[0] or "PLC status ON" in lines[0]:
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
        global execution

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
                if not execution_from_config:
                    self.enablePlayButton()
                    self.enableExitButton()
                else:
                    self.disablePlayButton()
                    self.enableResetButton()
                    self.enableStopButton()
                    self.disableOpenCSVButton()
                    self.disableExitButton()
            else:
                execution = False
                print("The path is invalid, values of duration, freq_list and others cannot be set.")


    def open_window_init(self):
        global execution_from_config
        global log_file
        self.ui.QoutputLabel.setText("Process started.")
        # Save log file
        date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        write_to_file(log_file, "{} {}".format(date_time, "Software ON, ready to start."))
        if execution_from_config:
            self.disablePlayButton()
            self.enableStopButton()
            self.enableResetButton()
            self.disableExitButton()
            self.disableOpenCSVButton()
        self.run_long_task()

    def play_execution(self):
        global log_file
        global config_file

        set_configfile_exec(config_file, "1")
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
        global config_file
        global no_resp_mode

        no_resp_mode = False # restore this flag
        set_configfile_exec(config_file, "0")
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
        global config_file
        global no_resp_mode

        set_configfile_exec(config_file, "0")
        no_resp_mode = False # restore this flag
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
        # date_time = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

        if plc_status:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(85, 255, 0);")
        else:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(255, 0, 0);")


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