# -*- coding: utf-8 -*-
"""
Created on Fri Oct 13 16:42:24 2023

@author: ronny
"""

import os


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
    with open(filename, "w") as f:
        f.write(content)
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