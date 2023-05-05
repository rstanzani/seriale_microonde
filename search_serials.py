# -*- coding: utf-8 -*-
"""
Created on Wed Feb 22 15:55:06 2023

@author: ronny
"""

import serial

#%% Old version
import glob
import sys

import serial.tools.list_ports

def serial_ports(): # the hard way, it finds also virtual com ports
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def serial_ports_compact():
    ports_new = serial.tools.list_ports.comports()

    port_list = []
    for port, desc, hwid in sorted(ports_new):
        port_list.append(str(port))
    # print(port_list)
    return port_list


def print_serials():
    list_serials = serial_ports_compact()
    printable = ""
    for ser in list_serials:
        printable += str(ser) + " "
    return printable


