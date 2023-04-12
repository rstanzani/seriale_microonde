# -*- coding: utf-8 -*-
"""
Created on Wed Feb 22 15:55:06 2023

@author: ronny
"""

import serial
import glob
import sys

def serial_ports():
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

print(serial_ports())




# ## https://stackoverflow.com/questions/12090503/listing-available-com-ports-with-python
# import serial.tools.list_ports
# ports = serial.tools.list_ports.comports()

# for port, desc, hwid in sorted(ports):
#         print("{}: {} [{}]".format(port, desc, hwid))