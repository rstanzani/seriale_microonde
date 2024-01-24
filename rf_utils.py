# -*- coding: utf-8 -*-
"""
Created on Fri Oct 13 16:42:24 2023

@author: ronny
"""

import os
import datetime


def Average(lst):
    avg = 0

    if len(lst) > 0:
        avg = round(sum(lst) / len(lst), 1)
    return avg


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

    def to_csv_string(self):
        return (str(self.Temperature) + ";" + str(self.PLL) + ";" + str(self.Current) + ";" + str(self.Voltage) + ";" + str(self.Reflected_Power) + ";" +
                str(self.Forward_Power) + ";" + str(self.PWM) + ";" + str(self.On_Off) + ";" + str(self.Enable_foldback) + ";" + str(self.Foldback_in) + ";" +
                str(self.Error) + ";" + str(self.cycle_count) + ";" + str(self.cycle_percentage) + ";\n")


def rf_time_values_log(filename, class_instance, verbose=False):
    if os.path.isfile(filename):
        pass
    else:
        f = open(filename, "w")
        f.write("datatime;Temperature;PLL;Current;Voltage;Reflected_Power;Forward_Power;PWM;On_Off;Enable_foldback;Foldback_in;Error;cycle_count;cycle_percentage;" + "\n") #name of the PLC values
        f.close()
    try:
        f = open(filename, "a")
        text = class_instance.to_csv_string()
        f.write(datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S") + ";" + text)
        f.close()
        if verbose:
            print("Logged at {}".format(datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")))
    except:
        pass # low priority log, so it is possible to skip in case something went wront (e.g. file opened by another program)


# def get_attributes(rfdata_instance,style="csv"): # not working if the values are not set, check
#     if style == "csv":
#         divider = ";"
#     else:
#         divider = " "
#     attributes = vars(rfdata_instance).items()
#     print("Attributes are {}".format(attributes))
#     attributes = ""
#     for key, attributes in attributes:
#         attributes += str(key) + divider
#     return attributes


class RFdataLists:
    '''Lists of the values used by logger.py'''

    target_Power = []
    forward_Power = []

    def reset(self):
        self.target_Power = []
        self.forward_Power = []

    def append_values(self, string):
        if len(string) == 2:
            if string[0] != "--": self.target_Power.append(float(string[0]))
            if string[1] != "--": self.forward_Power.append(float(string[1]))
        else:
            print("Wrong string.")

    def get_average(self):
        print("Avrg on {} values".format(len(self.target_Power)))
        return [Average(lst) for lst in [self.target_Power,self.forward_Power]]


def get_logger_values(rfdata):
    avrg_val = rfdata.get_average()

    strng = ""
    separator = " "
    for i in range(0, len(avrg_val)):
        strng += str(avrg_val[i]) + separator
    return strng


def write_to_file(filename, text):
    try:
        with open(filename, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    content = text + "\n" + content

    try:
        with open(filename, "w") as f:
            f.write(content)
    except:
        pass
    f.close()


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