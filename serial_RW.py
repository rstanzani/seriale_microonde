# -*- coding: utf-8 -*-
"""
Created on Thu Feb 23 17:20:07 2023

@author: ronny
"""
# import time
import random
from ast import literal_eval
import struct
import serial
import time
from binascii import hexlify


def connect_serial(comport="COM11"):
    # comport = "COM11"
    try:
        ser = serial.Serial(comport, 250000, timeout=0.1, bytesize=8) #nota: se metto un timeout dopo quel tempo mi legge tutto quello che ha ricevuto
        time.sleep(3)
        if (ser.isOpen()):
            print("Correctly opened port: {}".format(ser.name))
        return ser
    except:
        print("Error, maybe the port is already open.")

def rnd_hex_freq(randomize=True, list_val=[2420, 2480]):
    '''Return the hex of a random frequency in the range 2420-2480 MHz.
    list_val contains by default min and max frequency. The user can import
    a list of frequencies, but all elements should be even!'''
    if randomize:
        min_freq = 2420 #MHz, max freq is 2480 MHz
        num_freq = 30
        rnd = random.randint(0, num_freq)
        freq = min_freq + rnd*2
    else:
        if len(list_val) != 0:
            for elem in list_val:
                if elem%2 != 0:
                    print("Be careful! At least one value is not EVEN! I will use the standard list: [2420, 2480]")
                    list_val = [2420, 2480]
                    continue
        else:
           print("Be careful, the list is empty! I will use the standard list: [2420, 2480]")
           list_val = [2420, 2480]
        rnd = random.randint(0, len(list_val)-1)
        freq = list_val[rnd]

    # print(freq)
    freq_hex = float_to_hex(freq)
    converted = literal_eval(freq_hex) # Create the int with the hexadecimal value contained in the string (source: https://linuxhint.com/string-to-hexadecimal-in-python/)
    return converted


def float_to_hex(f):
    ''' Convert a float to a hex starting with 0x'''
    return hex(struct.unpack('<I', struct.pack('<f', f))[0])


def hex_to_float(h):
    ''' Convert a hex (with or without 0x) to a float'''
    h = h if h[0:2] != "0x" else h[2:]
    return struct.unpack('!f', bytes.fromhex(h))[0]


def checksum (start, address, payload_list):
    length = len(payload_list)
    # Bit sum

    somma = (start << 8 | address) + (length)

    for i in range(0, len(payload_list)):
        # print(hex(payload_list[i][2]))
        somma = somma + (payload_list[i][0] << 8 | payload_list[i][1])
        a, b = split_hex (payload_list[i][2])
        somma = somma + a + b

    # Checksum obtained by bitwise-AND and then a 8 bit shifting
    checksum = (somma & 0xff00) >> 8
    hex(checksum)
    return checksum


def split_hex (integer):
    '''Used to split a hex in two'''
    return divmod(integer, 0x10000)


def example_multiple_payloadlist():
    payload_list = []
    payload_list.append([0x01, 0x01, 0x41AFC800])
    payload_list.append([0x01, 0x02, 0x00000000])
    payload_list.append([0x01, 0x03, 0x403F9000])
    payload_list.append([0x01, 0x04, 0x41431400])
    payload_list.append([0x01, 0x05, 0x414B4B0C])
    payload_list.append([0x01, 0x06, 0x414646F6])
    return payload_list


def send_cmd(ser, start, address, length, typee, operand, content):

    # List of commands (a list for the general case) #TODO move this list to another point
    payload_list = []
    payload_list.append([typee, operand, content]) # Example to try a list of commands: payload_list = example_multiple_payloadlist()

    chksm = checksum(start, address, payload_list)
    # hex(chksm)

    header = start << 24 | address << 16 | len(payload_list) << 8 | chksm

    # Compose the payload command
    payload = 0x00
    for i in range(0, len(payload_list)):
        single_cmd = (payload_list[i][0] << 40) | (payload_list[i][1] << 32) | payload_list[i][2]
        payload = payload << 48 | single_cmd

    command = header << (len(payload_list) * 48) | payload

    # print("Sending the command {}".format(hex(command)))
    length_conversion = 4 + 6*len(payload_list)

    # print("Send:" + hex(command))
    ser.write(command.to_bytes(length_conversion, 'big'))


def send_cmd_string(ser, string, val=0, redundancy=1):
    for i in range(0, redundancy):
        value = val # do not remove, useful for the redundancy
        if string == "ON":
            send_cmd(ser, 0x55, 0x01, 0x01, 0x02, 0x0B, 0x00000001)
            time.sleep(0.3)
        elif string == "OFF":
            send_cmd(ser, 0x55, 0x01, 0x01, 0x02, 0x0B, 0x00000000)
        elif string == "STATUS":
            send_cmd(ser, 0x55, 0x01, 0x01, 0x01, 0x16, 0x00000000)
        elif string == "RNDFREQ":
            hex_freq = rnd_hex_freq(True)
            # print("Send freq {}".format(hex_freq))
            send_cmd(ser, 0x55, 0x01, 0x01, 0x02, 0x09, hex_freq)
        elif string == "READ_PWR":
            send_cmd(ser, 0x55, 0x01, 0x01, 0x01, 0x06, 0x00000000)
        elif string == "FLDBCK_ON":
            send_cmd(ser, 0x55, 0x01, 0x01, 0x02, 0x26, 0x1) # turn on
        elif string == "FLDBCK_VAL":
            if value != 0:
                value = hex(value)  # todo devono essere unsigned long
                value = literal_eval(value)
            else:
                value = 0x5 # default values 5W
            send_cmd(ser, 0x55, 0x01, 0x01, 0x02, 0x51, value) # set value
        elif string == "FLDBCK_READ":
            send_cmd(ser, 0x55, 0x01, 0x01, 0x01, 0x51, 0x00000000)
        elif string == "ERROR_READ":
            send_cmd(ser, 0x55, 0x01, 0x01, 0x01, 0x09, 0x00000000)
        elif string == "PWM_READ":
            send_cmd(ser, 0x55, 0x01, 0x01, 0x01, 0x08, 0x0)
        elif string == "V_READ":
            send_cmd(ser, 0x55, 0x01, 0x01, 0x01, 0x04, 0x0)
        elif string == "PWR":
            # print("Set power to: {}".format(value))
            if value != 0:
                value = float_to_hex(value)
                value = literal_eval(value)
            else:
                value = 0x00000000
            send_cmd(ser, 0x55, 0x01, 0x01, 0x02, 0x0E,  value)
            time.sleep(0.3)
        elif string == "PWM":
            if value != 0:
                value = hex(value)
                value = literal_eval(value)
            else:
                value = 0x00000000
            send_cmd(ser, 0x55, 0x01, 0x01, 0x02, 0x08,  value)
            time.sleep(0.3)
        elif string == "FREQ":
            if value != 0:
                value = float_to_hex(value)
                value = literal_eval(value)
            else:
                value = 0x00000000
            send_cmd(ser, 0x55, 0x01, 0x01, 0x02, 0x09,  value)
            time.sleep(0.3)
        else:
            print("Command not recognized!")



def read_reply_values(reply):
    '''Read reply payloads from the rf.
    Return a list of the read operands'''
    converted = hex(reply)[2:]
    error = False
    try:
        # Read the header structure
        start = converted[0:2]
        address = converted[2:4]
        length = int(converted[4:6], 16)
        # checksum = converted[6:8]
    except Exception as e:
        print("Error in serial_RW: {}, with converted equal to: {}".format(e, converted))
        error = True
        pass

    payload_list = []

    if not error:
        # TODO: read and analyze the checksum!
        if start == "55" and address == "00":
            for i in range(0, length):
                payload = converted[8+i*12:20+i*12]
                typee = payload[0:2]
                operand = payload[2:4]
                value = payload[4:12]
                if (len(payload) *  len(typee) *  len(operand) * len(value) != 0):
                    payload_list.append([typee, operand, value])
                    # print(value)
    return payload_list

#%% Updte status values

def empty_buffer(ser, wait=2):

    # read response
    start_waiting = time.time()

    send_cmd_string(ser,"STATUS")
    while time.time() <= start_waiting + wait:
        r = ser.read(100)
        if len(r) == 0:
            continue


def read_param(ser, rf_values, param="STATUS", wait=1, verbose=False):
    # read response
    start_waiting = time.time()

    send_cmd_string(ser, param)
    while time.time() <= start_waiting + wait:
        r = ser.read(100)
        if len(r) == 0:
            continue

        r_hex = hexlify(r)
        prova_int = int(r_hex, 16)

        # List of elements read from the serial
        payload_list = read_reply_values(prova_int)
        if len(payload_list) == 0:
            continue
        rf_values = set_status_values(rf_values, payload_list, False)
        if verbose:
            print_rfdata(rf_values, 2)
    return rf_values
    # return payload_list


def set_status_values (rf_values, payload_list, verbose=False):
    for i in range(0, len(payload_list)):
        operand = payload_list[i][1]
        if operand == "01":
            rf_values.Temperature = round(hex_to_float("0x"+str(payload_list[i][2])), 2)

        elif operand == "02":
            rf_values.PLL = int(payload_list[i][2], 16)

        elif operand == "03":
            rf_values.Current = round(hex_to_float("0x"+str(payload_list[i][2])), 2)

        elif operand == "04":
            rf_values.Voltage = round(hex_to_float("0x"+str(payload_list[i][2])), 2)

        elif operand == "05":
            rf_values.Reflected_Power = round(hex_to_float("0x"+str(payload_list[i][2])), 2)

        elif operand == "06":
           rf_values.Forward_Power = round(hex_to_float("0x"+str(payload_list[i][2])), 2)

        elif operand == "08":
           rf_values.PWM = int(payload_list[i][2], 16)

        elif operand == "0B" or operand == "0b":
           rf_values.On_Off = int(payload_list[i][2], 16)

        elif operand == "26":
           rf_values.Enable_foldback = int(payload_list[i][2], 16)

        elif operand == "51":
           rf_values.Foldback_in = int(payload_list[i][2], 16)

        elif operand == "17":
           rf_values.Error = int(payload_list[i][2], 16)
    if verbose:
        print("Status updated")
    return rf_values

def print_rfdata(rf_data, verbose=0):
    '''Verbose level [0,1,2] serves to select how many values to plot.'''

    if verbose == 0: # Do NOT remove ending spaces, they are useful when printing on and old and longer line
        print("\r", "On Off: {} || Reflected Power: {} [W] || Forward Power: {} [W] || Enable foldback: {} || Error: {}      \r".format(rf_data.On_Off, rf_data.Reflected_Power, rf_data.Forward_Power, rf_data.Enable_foldback, rf_data.Error))

    if verbose == 1:
        print("\r", "On Off: {} || Temperature: {} [C] ||  Current: {} [A] || Voltage: {} [V] || Reflected Power: {} [W] || Forward Power: {} [W] || Enable foldback: {} || Foldback in {} [W] || Error: {}      \r".format(rf_data.On_Off, rf_data.Temperature, rf_data.Current, rf_data.Voltage, rf_data.Reflected_Power, rf_data.Forward_Power, rf_data.Enable_foldback, rf_data.Foldback_in, rf_data.Error))

    if verbose == 2:
        print("\r", "On Off: {} || Temperature: {} [C] || PLL: {} || Current: {} [A] || Voltage: {} [V] || Reflected Power: {} [W] || Forward Power: {} [W] || PWM: {} || Enable foldback: {} || Foldback in {} [W] || Error: {}      \r".format(rf_data.On_Off, rf_data.Temperature, rf_data.PLL, rf_data.Current, rf_data.Voltage, rf_data.Reflected_Power, rf_data.Forward_Power, rf_data.PWM, rf_data.Enable_foldback, rf_data.Foldback_in, rf_data.Error))

