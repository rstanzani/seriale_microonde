import serial_RW as srw
import serial  # maybe try to import "serial.rs485"
from binascii import hexlify   # https://stackoverflow.com/questions/16748083/print-without-b-prefix-for-bytes-in-python-3
# prova = hexlify(b'U\x00\x0b\xdd\x01\x01A\xa5\xa0\x00\x01\x02\x00\x00\x00\x01\x01\x03?\xa1@\x00\x01\x04A\xfe\xbc\t\x01\x05\x00\x00\x00\x00\x01\x06?"\xdd\xf8\x01\x08\x00\x00\x00Y\x01\x07\x00\x00\x00N\x01%\x00\x00\x00\x01\x01\x0b\x00\x00\x00\x01\x01&\x00\x00\x00\x00')
import time
import read_csv as rcsv
import data_interface as dtf

status = {"Temperature":"ND","PLL":"ND","Current":"ND","Voltage":"ND","Reflected Power":"ND", 
          "Forward Power":"ND", "PWM":"ND", "On Off":"ND", "Enable foldback":"ND", "Foldback in":"ND", "Error":"No error"}

# Main ########################################################################
comport = "COM11"
ser = serial.Serial(comport, 250000, timeout=0.1, bytesize=8) #nota: se metto un timeout dopo quel tempo mi legge tutto quello che ha ricevuto
if (ser.isOpen()):
    print("Correctly opened port: {}".format(ser.name))

# Read parameters from csv file
duration, freq_list, power_list = rcsv.read_and_plot("D:\Downloads\Book2.rf.csv", True, False)

index = 0
next_time = duration[0]
freq = freq_list[0]
power = power_list[0]

srw.send_cmd_string(ser,"ON")
srw.send_cmd_string(ser,"PWR", power)
srw.send_cmd_string(ser,"FREQ", freq)
srw.send_cmd_string(ser,"FLDBCK_ON")
srw.send_cmd_string(ser,"FLDBCK_VAL", 5)

init_time = time.time()
print("At {} Power and freq are now: {} {}".format(time.time()-init_time, power, freq))
while time.time()-init_time <= sum(duration):
    
    if time.time()-init_time >= next_time:
        index += 1
        if index < len(duration):
            next_time = next_time + duration[index]
            power = power_list[index]
            freq = freq_list[index]
            print("At {} Power and freq are now: {} {}".format(time.time()-init_time, power, freq))
        srw.send_cmd_string(ser,"PWR", power)
        srw.send_cmd_string(ser,"FREQ", freq)

    # read response
    start_waiting = time.time()

    srw.send_cmd_string(ser,"STATUS")
    while time.time() <= start_waiting + 1:
        r = ser.read(100)
        if len(r) == 0:
            continue      
        
        r_hex = hexlify(r)
        prova_int = int(r_hex, 16)
        payload_list = srw.read_reply_values(prova_int)
        if len(payload_list) == 0:
            continue
        dtf.set_status_values(status, payload_list, False)
        dtf.print_status(status, 0)
        
# Soft turn off
print("Start soft shut down...")
srw.send_cmd_string(ser,"PWR", 0)
srw.send_cmd_string(ser,"OFF")

# Close ports
ser.close()
