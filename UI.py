from PyQt5 import QtCore # QtGui, QtWidgets
# from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThreadPool
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow #QWidget, QInputDialog, QLineEdit
from PyQt5.QtCore import pyqtSignal # QThread

import read_csv as rcsv
import serial_RW as srw
import plc_socket as plcsk
from UI_raw import Ui_MainWindow
import rf_utils as rfu

import os
import time
import datetime
import logging
import psutil
import zmq
import sys

# TODO list:
# (001) - do something when serial_error = True
# (002) - check if it's useful or not

config_file = "config.csv"
comport, csv_name, execution_from_config = rfu.read_config(config_file)

class Worker(QtCore.QObject):
    messaged = pyqtSignal()
    finished = pyqtSignal()
    ser = None
    serial_open = 0
    context = None
    socket = None
    safe_mode_param = 1 # base value 1, in safe mode 2/3
    duration = [0]
    freq_list = []
    power_list = []
    power = 0
    freq = 2450
    index = 0
    remaining_cycle_time = 60
    threshold_security_mode = False
    starttime_security_mode = 0
    duration_security_mode = 30 # seconds
    safety_mode_counter = 0
    force_change_pwr_safety = False
    noresp_counter = 0
    min_refresh = 0.3  # minimum refresh rate
    plc_status = 0
    old_plc_status = 0
    rf_data = rfu.RFdata()
    threshold_stop = False
    interruption_type = "reset" # "stop" or "reset" (default value)
    num_executed_cycles = 1
    execution_time = 0
    prev_execution_time = 0
    thres_status = ""
    no_resp_mode = False
    log_file = "log.txt"
    rf_CSV_name = "rfvalueslog.csv"
    thread_exec = True
    execution = False
    serial_error = False

    # New variable to count the number of errors from the socket reading
    sckt_err_count = 0

    # Socket for sending rf data to logger
    context_pub = None
    socket_pub = None
    topic_pub = None

    def rf_log(self, text):
      rfu.write_to_file(self.log_file, "{} {}".format(datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"), text))


    def stop_worker_execution(self):
        if self.execution:
            self.execution = False
        else:
            print("Execution stopped.")


    def close_socket(self):
        self.socket.close()
        self.context.term()
        print("Socket closed")


    def close_socket_pub(self):
        self.socket_pub.close()
        self.context_pub.term()
        print("Publisher socket closed")


    def close_serial(self):
        '''Close the serial connection'''
        self.ser.close()
        print("COM port correctly closed")


    def start_execution(self):
        print("Started execution in Worker")
        self.execution = True


    def check_thresholds(self, rf_data):
        '''Check the thresholds and return a bool'''

        thres_exceeded = False
        if rf_data.Temperature != "--" and rf_data.Voltage != "--" and rf_data.Current != "--" and rf_data.Reflected_Power != "--" and rf_data.Forward_Power != "--":
            if int(rf_data.Temperature) >= 65 or int(rf_data.Voltage) >= 33 or int(rf_data.Current) >= 18 or int(rf_data.Reflected_Power) >= 150 or int(rf_data.Forward_Power) >= 260:
                self.thres_status = "Threshold Err. Temp {}C, Volt {}V, Curr {}A, R.Pow {}W, Pow {}W".format(rf_data.Temperature,rf_data.Voltage,rf_data.Current,rf_data.Reflected_Power,rf_data.Forward_Power)
                thres_exceeded = True
        return thres_exceeded


    def safe_mode(self, rf_data):
        '''Change the state of the system based on the thresholds.'''

        if not self.threshold_security_mode:
            if self.check_thresholds(rf_data):
                print("Entering SAFE MODE, status: {}".format(self.thres_status))
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
                            self.threshold_stop = True
                    else:
                        print("Exiting from Safe Mode.")
                        self.safe_mode_param = 1
                        self.safety_mode_counter = 0
                        self.threshold_security_mode = False
                        self.starttime_security_mode = 0
                        self.force_change_pwr_safety = True


    def run(self):
        print("In run...")
        global comport
        first_no_resp = True

        turn_on = True
        just_turned_off = True   #when the user click STOP or RESET buttons

        self.safe_mode_param = 1
        self.safety_mode_counter = 0
        self.threshold_security_mode = False
        self.starttime_security_mode = 0

        prev_noresp_time = time.time()

        # Open subscriber socket
        self.context, self.socket = plcsk.subscriber("5432", "1001")

        # Start publisher socket
        self.topic_pub = 2002
        self.context_pub, self.socket_pub = plcsk.publisher("5433", self.topic_pub)
        # self.socket_pub.setsockopt(zmq.LINGER, 100) # TODO (002)

        # Check the connection to the serial
        print("Opening connection with RF...")
        self.ser, self.serial_open = srw.connect_serial(comport)

        timestamp_plc_check = time.time()
        plc_check_refresh = 1 # second

        timestamp_rf_check = time.time()
        rf_check_refresh = 6 # second(s) # for sending rf data to the logger, double of the reading frequency

        while self.thread_exec:

            # Read PLC status from socket
            if time.time() >= timestamp_plc_check + plc_check_refresh:

                # Read plc status from socket
                try:
                    string = self.socket.recv(zmq.NOBLOCK)
                    _, skt_val = string.split()

                    self.plc_status = False if str(skt_val) == "b'0'" else True
                    self.sckt_err_count = 0
                except zmq.error.Again:
                    self.sckt_err_count += 1
                    print("EAGAIN error from zmq (e.g. no message from publisher).")
                except:
                    self.plc_status = False
                    print("No message from socket. PLC status set to False.")
                timestamp_plc_check = time.time()
                if self.sckt_err_count >= 2:
                    self.plc_status = False

            if time.time() >= timestamp_rf_check + rf_check_refresh:
                # Send rf data to the logger
                try:
                    rfstr = str(self.power) + " " + str(self.rf_data.Forward_Power)
                    self.socket_pub.send_string("{} {}".format(self.topic_pub, rfstr))
                except:
                    print("Socket error: message not sent")
                timestamp_rf_check = time.time()

            stopwatch_START = time.time() # START for the stopwatch for the cycle

            # No response from serial Mode
            if self.no_resp_mode:
                if time.time() - prev_noresp_time >= 10:  # each 10 seconds it checks
                    print("In no response mode")
                    if self.execution == False and not self.threshold_stop and self.plc_status: # restore execution after a stop from serial not responding
                        self.execution = True
                        srw.send_cmd_string(self.ser,"ON")
                        print("Restored from no_resp_mode")
                    prev_noresp_time = time.time()

            # ACTIVE STATUS
            if self.execution and self.serial_open and not self.threshold_stop and self.plc_status:

                # First turn on
                if turn_on:
                    # Initialize or reset variables only after a Reset state
                    if self.interruption_type == "reset":
                        if isinstance(self.duration, list):
                            self.remaining_cycle_time = self.duration[0]
                            self.freq = self.freq_list[0]
                            self.power = self.power_list[0]
                        self.prev_execution_time = 0

                    # Set parameters to the RF generator
                    srw.send_cmd_string(self.ser,"PWR", 0, redundancy=3)
                    srw.empty_buffer(self.ser, wait=1)
                    srw.send_cmd_string(self.ser,"FLDBCK_ON", redundancy=3)
                    srw.empty_buffer(self.ser, wait=0.5)
                    srw.send_cmd_string(self.ser,"FLDBCK_VAL", 5, redundancy=3)
                    srw.empty_buffer(self.ser, wait=0.5)
                    srw.send_cmd_string(self.ser,"FREQ", self.freq, redundancy=1)
                    srw.send_cmd_string(self.ser,"PWR", self.power*self.safe_mode_param, redundancy=3)

                    self.rf_log("RF on")

                    # TODO (001)
                    self.serial_error, self.rf_data, self.noresp_counter = srw.read_param(self.ser, self.noresp_counter, self.rf_data, "STATUS", 1, False)
                    rfu.rf_time_values_log(self.rf_CSV_name, self.rf_data, False, self.freq)  # log rf values on file

                    time.sleep(0.2)

                    # Start the main functions
                    timestamp = time.time()
                    starttime = time.time()
                    turn_on = False
                    just_turned_off = True

                if self.rf_data.On_Off == 0:
                    # This state can happen when the time between two messages on the serial where too long and the RF generator turned off.
                    print("Restore")
                    check = False
                    while check == False:
                        self.serial_error = srw.send_cmd_string(self.ser,"ON")

                        self.serial_error, self.rf_data, self.noresp_counter = srw.read_param(self.ser, self.noresp_counter, self.rf_data, "STATUS", 1, False)
                        time.sleep(1)
                        if self.rf_data.On_Off == 1:
                            
                            # Change frequency cycle: power to 0W > set frequency > set desired power
                            self.serial_error = srw.send_cmd_string(self.ser,"PWR", 0, redundancy=3, sleep_time=0.1)
                            self.serial_error = srw.send_cmd_string(self.ser,"FREQ", self.freq, redundancy=3, sleep_time=0.3)
                            self.serial_error = srw.send_cmd_string(self.ser,"PWR", self.power*self.safe_mode_param, redundancy=3, sleep_time=0.1)
                            
                            check = True
                            self.rf_data.Error = 0

                # Normal cycle with the selected refresh rate
                if time.time() >= timestamp + self.min_refresh:

                    if self.noresp_counter >= 30:
                        if first_no_resp:
                            print("Exit: no Response from serial!")
                            first_no_resp = False
                        if not self.no_resp_mode:
                            # Update log file
                            self.rf_log("Stopped execution: no response from serial")
                            print("Stopped execution: no response from serial")
                            self.no_resp_mode = True
                            self.execution = False
                            self.rf_data.On_Off = 0
                            self.rf_data.reset()
                            self.prev_execution_time = self.execution_time

                    self.safe_mode(self.rf_data)
                    if self.force_change_pwr_safety:
                        self.serial_error = srw.send_cmd_string(self.ser,"PWR", self.power*self.safe_mode_param, redundancy=3, sleep_time=0.2)

                        self.force_change_pwr_safety = False

                    if self.remaining_cycle_time <= 0:    # change the cycle position when the remaining time for this cycle is finished
                        self.index += 1
                        self.index = self.index % len(self.duration)  # set to 0 if is the last line in the csv

                        self.remaining_cycle_time = self.duration[self.index]
                        self.power = self.power_list[self.index]
                        self.freq = self.freq_list[self.index]
                        if self.index == 0:
                            self.num_executed_cycles += 1

                        # Change frequency cycle: power to 0W > set frequency > set desired power
                        self.serial_error = srw.send_cmd_string(self.ser,"PWR", 0, redundancy=3, sleep_time=0.05)
                        self.serial_error = srw.send_cmd_string(self.ser,"FREQ", self.freq, redundancy=3, sleep_time=0.1)
                        self.serial_error = srw.send_cmd_string(self.ser,"PWR", self.power*self.safe_mode_param, redundancy=3, sleep_time=0.05)

                    # print("Ask for status")
                    self.serial_error, self.rf_data, self.noresp_counter = srw.read_param(self.ser, self.noresp_counter, self.rf_data, "STATUS", 1, False)
                    rfu.rf_time_values_log(self.rf_CSV_name, self.rf_data, False, self.freq) # log rf values on file

                    # Note: the self.noresp_counter almost never gives perfect 0 due to the various messages that can be lost
                    if self.no_resp_mode:
                        if self.noresp_counter <= 10:
                            self.no_resp_mode = False
                            first_no_resp = True
                            starttime = time.time()  # reset the timer count after a connection restore
                    self.rf_data.cycle_count = self.num_executed_cycles
                    self.rf_data.cycle_percentage = round(self.index/(len(self.duration))*100, 0)
                    self.messaged.emit()
                    timestamp = time.time()

                    if not self.no_resp_mode:
                        self.execution_time = self.prev_execution_time + (timestamp - starttime) # calculate the total execution time for the RF generator
                    if self.rf_data.Error == 4:
                        print("Re-set parameters")
                        self.serial_error = srw.send_cmd_string(self.ser,"PWR", 0, redundancy=3, sleep_time=0.05)
                        self.serial_error = srw.send_cmd_string(self.ser,"FREQ", self.freq, redundancy=3, sleep_time=0.1)
                        self.serial_error = srw.send_cmd_string(self.ser,"PWR", self.power*self.safe_mode_param, redundancy=3, sleep_time=0.05)

                        
                    if self.rf_data.Error == 203:   #writing not enabled (probably off?)
                        print("Restart")

                        check = False
                        while check == False:
                            self.serial_error = srw.send_cmd_string(self.ser,"ON")
                            self.serial_error, self.rf_data, self.noresp_counter = srw.read_param(self.ser, self.noresp_counter, self.rf_data, "STATUS", 1, False)

                            time.sleep(1)
                            if self.rf_data.On_Off == 1:
                                self.serial_error = srw.send_cmd_string(self.ser,"PWR", 0, redundancy=3, sleep_time=0.05)
                                self.serial_error = srw.send_cmd_string(self.ser,"FREQ", self.freq, redundancy=3, sleep_time=0.1)
                                self.serial_error = srw.send_cmd_string(self.ser,"PWR", self.power*self.safe_mode_param, redundancy=3, sleep_time=0.05)
                                check = True
                                self.rf_data.Error = 0
            elif just_turned_off:
                print("\nShutting down...")

                self.serial_error = srw.send_cmd_string(self.ser,"PWM", 0, 2)
                self.serial_error = srw.send_cmd_string(self.ser,"OFF")

                self.serial_error = srw.empty_buffer(self.ser, wait=1)

                self.prev_execution_time = self.execution_time
                self.serial_error, self.rf_data, self.noresp_counter = srw.read_param(self.ser, self.noresp_counter, self.rf_data, "STATUS", 1, False)
                rfu.rf_time_values_log(self.rf_CSV_name, self.rf_data, False, self.freq)  # log rf values on file

                turn_on = True # used to re-set parameters in the next turn on
                just_turned_off = False

            # IDLE STATUS
            else:
                if not 'timestamp' in locals(): # timestamp is not defined if it does not enter in the previous IF (e.g. if pls_status is off when turning on)
                    timestamp = time.time()
                if time.time() >= timestamp + self.min_refresh:
                    # print("I am in IDLE mode!")
                    self.serial_error, self.rf_data, self.noresp_counter = srw.read_param(self.ser, self.noresp_counter, self.rf_data, "STATUS", 1, False)
                    self.messaged.emit()

            # check plc variation
            if self.old_plc_status != self.plc_status:
                print("PLC status is changed.")
                if self.plc_status:
                    self.rf_log("PLC status ON.")
                else:
                    self.rf_log("PLC status OFF.")

            self.old_plc_status = self.plc_status
            stopwatch_STOP = time.time()
            if not self.no_resp_mode and str(self.rf_data.On_Off) == "1":
                self.remaining_cycle_time -= stopwatch_STOP - stopwatch_START # reduce the time only when the RF is working

        # Soft turn off
        print("Main thread killed by the user, shut down and close serial")
        self.rf_data.reset()

        self.messaged.emit()
        self.finished.emit()


class MainWindow(QMainWindow):
    ui = None
    error = ""
    msg = ""
    error_history = []
    worker = None
    thread = None
    last_status_update = 0
    is_plot_present = False # tells if the csv plot is already present and therefore will be overwritten by another csv


    def __init__(self):
        global csv_name
        global execution_from_config

        self.__thread = QtCore.QThread()

        self.worker = Worker()

        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.QOpen_CSV.clicked.connect(lambda: self.open_file("Open_CSV"))
        self.ui.Qexit.clicked.connect(lambda: self.close())

        # read from csv
        self.worker.duration, self.worker.freq_list, self.worker.power_list, self.error, self.msg  = rcsv.read_and_plot(self.ui, csv_name, self.is_plot_present)
        if not self.error:
            self.ui.Qcsvpath.setText(csv_name)
            self.is_plot_present = True
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
            self.worker.execution = False
            print("The path is invalid, values of duration, freq_list and others cannot be set.")

		# Disable the X close button
        self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)

        self.open_window_init()    # init the functionalities when opening the program
        self.ui.Qplay.clicked.connect(lambda: self.play_execution())
        self.ui.Qstop.clicked.connect(lambda: self.stop_execution())
        self.ui.Qreset.clicked.connect(lambda: self.reset_execution())


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


    def __get_thread(self):
        self.thread = QtCore.QThread()
        self.worker.moveToThread(self.thread)

        # this is essential when worker is in local scope!
        self.thread.worker = self.worker
        self.thread.started.connect(self.worker.run)
        self.worker.messaged.connect(lambda: self.update_status())
        self.worker.finished.connect(lambda: self.quit_thread())
        return self.thread


    def quit_thread(self):
        self.thread.quit


    def restore_buttons(self):
        self.enablePlayButton()
        if self.worker.interruption_type == "stop":
            self.disableStopButton()
            self.ui.QoutputLabel.setText("Process stopped.")
        elif self.worker.interruption_type == "reset":
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

        # Reads the file path from the prompt
        self.disablePlayButton()
        file_type = button_name.split("_")[1]
        path = ""

        opened_path, _ = QFileDialog.getOpenFileName(None, "Open the {} file".format(file_type), path, "*")
        # Read parameters from csv file
        if opened_path != "":
            self.ui.Qcsvpath.setText(opened_path)
            self.worker.duration, self.worker.freq_list, self.worker.power_list, self.error, self.msg  = rcsv.read_and_plot(self.ui, opened_path, self.is_plot_present)

            self.ui.QoutputLabel.setText(self.msg)
            if not self.error:
                self.is_plot_present = True
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
                self.worker.execution = False
                print("The path is invalid, values of duration, freq_list and others cannot be set.")


    def set_configfile_exec(self, path, state):
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


    def open_window_init(self):
        global execution_from_config
        self.ui.QoutputLabel.setText("Process started.")
        # Save log file
        self.worker.rf_log("Software ON, ready to start.")
        if execution_from_config:
            self.disablePlayButton()
            self.enableStopButton()
            self.enableResetButton()
            self.disableExitButton()
            self.disableOpenCSVButton()
        self.run_long_task()

    def play_execution(self):
        global config_file

        self.set_configfile_exec(config_file, "1")
        self.disablePlayButton()
        self.enableStopButton()
        self.enableResetButton()
        self.disableExitButton()
        self.disableOpenCSVButton()
        self.worker.start_execution()


    def reset_execution(self):
        global config_file

        self.worker.no_resp_mode = False # restore this flag
        self.set_configfile_exec(config_file, "0")
        self.worker.interruption_type = "reset"
        self.worker.num_executed_cycles = 1
        self.worker.rf_log("Reset")
        self.ui.QoutputLabel.setText("Process reset.")
        self.worker.stop_worker_execution()
        self.worker.index = 0
        self.restore_buttons()


    def stop_execution(self):
        global config_file

        self.set_configfile_exec(config_file, "0")
        self.worker.no_resp_mode = False # restore this flag
        self.worker.interruption_type = "stop"
        self.worker.rf_log("Stop")
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

        self.worker.thread_exec = False
        if self.thread:
            self.thread.quit

        time.sleep(3)

        # Close socket and serial
        self.worker.close_socket()
        self.worker.close_serial()
        self.worker.close_socket_pub()

        # Identify the app closing on the log file
        rfu.write_to_file(self.worker.log_file, "{}".format("--"))
        print("Window closing...")
        QApplication.quit()


    def update_status(self):
        _translate = QtCore.QCoreApplication.translate
        self.ui.Qtemperature_label.setText(_translate("MainWindow", str(self.worker.rf_data.Temperature)+" °C"))
        self.ui.Qpll_label.setText(_translate("MainWindow", str(self.worker.rf_data.PLL)))
        self.ui.Qcurrent_label.setText(_translate("MainWindow", str(self.worker.rf_data.Current))+" A")
        self.ui.Qvoltage_label.setText(_translate("MainWindow", str(self.worker.rf_data.Voltage))+" V")
        self.ui.Qreflectedpower_label.setText(_translate("MainWindow", str(self.worker.rf_data.Reflected_Power)+" W"))
        self.ui.Qforwardpower_label.setText(_translate("MainWindow", str(self.worker.rf_data.Forward_Power)+" W"))
        self.ui.Qpwm_label.setText(_translate("MainWindow", str(self.worker.rf_data.PWM)))
        if str(self.worker.rf_data.On_Off) == "1":
            self.ui.Qonoff_label.setText(_translate("MainWindow", "On"))
            self.ui.Qonoff_label.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(85, 255, 0);")
        else:
            self.ui.Qonoff_label.setText(_translate("MainWindow", "Off"))
            self.ui.Qonoff_label.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(255, 0, 0);")

        if self.worker.threshold_stop:
            self.ui.QoutputLabel.setText("THRESHOLD ALARM, see log file.")
            self.worker.rf_log(self.worker.thres_status)
            self.worker.threshold_stop = False
            self.worker.interruption_type = "reset"

        self.ui.Qfrequency.setText(_translate("MainWindow", str(self.worker.freq)))

        self.ui.Qenablefoldback_label.setText(_translate("MainWindow", str(self.worker.rf_data.Enable_foldback)))
        self.ui.Qfoldbackin_label.setText(_translate("MainWindow", str(self.worker.rf_data.Foldback_in)+" W"))
        self.ui.Qerror_label.setText(_translate("MainWindow", str(self.worker.rf_data.Error)))
        self.ui.Qcyclenumber.setText(_translate("MainWindow", str(self.worker.rf_data.cycle_count)))
        self.ui.Qcurrentcycle.setText(_translate("MainWindow", str(self.worker.rf_data.cycle_percentage)))
        self.ui.Qexecution_time.setText(_translate("MainWindow", str(datetime.timedelta(seconds = int(self.worker.execution_time)))))

        if time.time() > self.last_status_update + 60:
            self.status_log_file(self.worker.log_file, "{} - cycle num: {} - cycle progress: {}%".format(datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"), self.worker.rf_data.cycle_count, self.worker.rf_data.cycle_percentage))
            self.last_status_update = time.time()


        if self.worker.plc_status:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(85, 255, 0);")
        else:
            self.ui.QPLCInfo.setStyleSheet("color: rgb(41, 45, 62);\n"
                                             "background-color: rgb(255, 0, 0);")


if __name__ == "__main__":
    name = "UI.exe"
    logging.basicConfig(filename=f'{os.getcwd()}\\UI_err.log', level=logging.ERROR,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    err_logger = logging.getLogger(__name__)
    if not name in (p.name() for p in psutil.process_iter()):
        try:
            app = QApplication(sys.argv)
            window = MainWindow()
            window.show()
            sys.exit(app.exec())
        except Exception as err:
            print("Exception occurred in __main__ execution! ")
            err_logger.error(err)
    else:
        err_logger.error(f"{name} is already open!")
        print(f"{name} is already open!")