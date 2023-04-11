# -*- coding: utf-8 -*-
"""
Created on Tue Apr 11 16:13:21 2023

@author: ronny
"""
import struct

def hex_to_float(h):
    ''' Convert a hex (with or without 0x) to a float'''
    h = h if h[0:2] != "0x" else h[2:]
    return struct.unpack('!f', bytes.fromhex(h))[0]


def set_status_values (status, payload_list, verbose=False):
    for i in range(0, len(payload_list)):
        operand = payload_list[i][1]
        if operand == "01":
            if verbose: print("Temperature")
            status["Temperature"] = round(hex_to_float("0x"+str(payload_list[i][2])), 2)
            
        elif operand == "02":
            if verbose: print("PLL")
            status["PLL"] = int(payload_list[i][2], 16)  # conversion from Unsigned Long
            
        elif operand == "03":
            if verbose: print("Current")
            status["Current"] = round(hex_to_float("0x"+str(payload_list[i][2])), 2)
            
        elif operand == "04":
            if verbose: print("Voltage")
            status["Voltage"] = round(hex_to_float("0x"+str(payload_list[i][2])), 2)
            
        elif operand == "05":
            if verbose: print("Reflected Power")
            status["Reflected Power"] = round(hex_to_float("0x"+str(payload_list[i][2])), 2)
            
        elif operand == "06":
           if verbose: print("Forward Power")
           status["Forward Power"] = round(hex_to_float("0x"+str(payload_list[i][2])), 2)
           
        elif operand == "08":
           if verbose: print("PWM")
           status["PWM"] = int(payload_list[i][2], 16)
            
        elif operand == "0B" or operand == "0b":
           if verbose: print("On Off")
           status["On Off"] = int(payload_list[i][2], 16)
           
        elif operand == "26":
           if verbose: print("Enable foldback")
           status["Enable foldback"] = int(payload_list[i][2], 16)
           # status["Foldback power"] = hex_to_float("0x"+str(payload_list[i][2])) #TODO controllare che sia un long unsigned!
           
        elif operand == "51":
           if verbose: print("Foldback in")
           status["Foldback in"] = int(payload_list[i][2], 16)
           # status["Foldback power"] = hex_to_float("0x"+str(payload_list[i][2])) #TODO controllare che sia un long unsigned!
            
        elif operand == "17":
           if verbose: print("Error")
           status["Enable foldback"] = int(payload_list[i][2], 16)
           
    print("Status updated")

def print_status(status, verbose=0):
    '''Verbose level [0,1,2] serves to select how many values to plot.'''

    if verbose == 0:
        print("\r", "On Off: {} || Reflected Power: {} [W] || Forward Power: {} [W] || Enable foldback: {} || Error: {}".format(status["On Off"], status["Reflected Power"], status["Forward Power"], status["Enable foldback"], status["Error"]), end="")

    if verbose == 1:
        print("\r", "On Off: {} || Temperature: {} [C] ||  Current: {} [A] || Voltage: {} [V] || Reflected Power: {} [W] || Forward Power: {} [W] || Enable oldback: {} || Foldback in {} || Error: {}".format(status["On Off"],status["Temperature"], status["Current"], status["Voltage"], status["Reflected Power"], status["Forward Power"], status["Enable foldback"], status["Foldback in"], status["Error"]), end="")

    if verbose == 2:
        print("\r", "On Off: {} || Temperature: {} [C] || PLL: {} || Current: {} [A] || Voltage: {} [V] || Reflected Power: {} [W] || Forward Power: {} [W] || PWM: {} || Enable oldback: {} || Foldback in {} || Error: {}".format(status["On Off"],status["Temperature"], status["PLL"], status["Current"], status["Voltage"], status["Reflected Power"], status["Forward Power"], status["PWM"], status["Enable foldback"], status["Foldback in"], status["Error"]), end="")
