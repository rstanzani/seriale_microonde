from PyQt5 import QtCore # QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow #QWidget, QInputDialog, QLineEdit
import time
import read_csv as rcsv
import serial_RW as srw
from UI_raw import Ui_MainWindow


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
    execution = False

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.QOpen_CSV.clicked.connect(lambda:  self.open_file("Open_CSV"))

        self.ui.Qexit.clicked.connect(lambda: self.close())

        self.ui.Qplay.clicked.connect(lambda: self.play_execution())      
        self.ui.Qpause.clicked.connect(lambda: self.pause_execution())
        self.ui.Qstop.clicked.connect(lambda: self.stop_execution())


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
        self.execution = True
        
        ser = srw.connect_serial("COM9")
        # Initialize
        index = 0
        next_time = self.duration[0]
        freq = self.freq_list[0]
        power = self.power_list[0]

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
                self.update_values_on_screen(MainWindow)
                self.save_error_log()
                timestamp = time.time()

        # Soft turn off
        print("\nStart soft shut down...")
        srw.send_cmd_string(ser,"OFF")
        srw.send_cmd_string(ser,"PWM", 0)
        srw.empty_buffer(ser, self.status, wait=1)
        print("\nRead status to confirm shutdown:")
        self.status = srw.read_param(ser, self.status, "STATUS")
        # Close ports
        ser.close()
        print("THE TYPE OF THE FILE IS:")
        print(type(self.status["Forward Power"]))
        self.update_values_on_screen(MainWindow)
        
        self.enablePlayButton()
        self.disableStopButton()
        self.disablePauseButton()

        
    def pause_execution(self):
        #define pause
        return
        
    def stop_execution(self):
        self.execution = False


    def update_values_on_screen(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        self.ui.Qtemperature_label.setText(_translate("MainWindow", str(self.status["Temperature"])))
        self.ui.Qpll_label.setText(_translate("MainWindow", str(self.status["PLL"])))
        self.ui.Qcurrent_label.setText(_translate("MainWindow", str(self.status["Current"])))
        self.ui.Qvoltage_label.setText(_translate("MainWindow", str(self.status["Voltage"])))
        self.ui.Qreflectedpower_label.setText(_translate("MainWindow", str(self.status["Reflected Power"])))
        self.ui.Qforwardpower_label.setText(_translate("MainWindow", str(self.status["Forward Power"])))
        self.ui.Qpwm_label.setText(_translate("MainWindow", str(self.status["PWM"])))
        self.ui.Qonoff_label.setText(_translate("MainWindow", str(self.status["On Off"])))
        self.ui.Qenablefoldback_label.setText(_translate("MainWindow", str(self.status["Enable foldback"])))
        self.ui.Qfoldbackin_label.setText(_translate("MainWindow", str(self.status["Foldback in"])))
        self.ui.Qerror_label.setText(_translate("MainWindow", str(self.status["Error"])))


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


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())