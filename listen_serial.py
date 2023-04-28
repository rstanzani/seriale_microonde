# -*- coding: utf-8 -*-
"""
Created on Wed Feb 22 14:13:27 2023

@author: ronny
"""

import serial_RW as srw
import serial
# import random
# from ast import literal_eval
# import struct

ser = serial.Serial('COM10', 250000, timeout=0.5, bytesize=8)
# serial1.close()

# random_values = [0x00000010]
def fake_responses(ser, string, value=0):
    if string == "PWR":
        # srw.send_cmd(ser, 0x55, 0x00, 0x01, 0x01, 0x06, 0x41CA6666)
        srw.send_cmd_string(ser,"PWR", 50)
        # srw.send_cmd(ser, 0x55, 0x00, 0x01, 0x01, 0x06, random_values[random.randint(0,len(random_values)-1)])
    else:
        print("Command not recognized!")

def read_forever(ser):
    while True:
        r = ser.read(10)
        if len(r) == 0:
            continue
        print(r)
        fake_responses(ser, "PWR")

read_forever(ser)





