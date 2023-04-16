
import time
import read_csv as rcsv
import serial_RW as srw
from datetime import datetime
# import threading
import signal

# Part to manage the exit with cterl+c
exit_flag = False  # Global variable to track exit status

def handler(signum, frame):
    global exit_flag  # Declare the use of global variable
    msg = "\n Ctrl-c was pressed. Do you want to EXIT and turn off the RF? y/n \n "
    print(msg, end="", flush=True)
    res = input()
    if res in ('y', 'Y', 'yes', 'Yes'):
        exit_flag = True  # Set exit_flag to True to indicate exit
 
signal.signal(signal.SIGINT, handler)

def save_error_log():
    global status
    global error_history
    to_add = False

    if status["Error"] != "No error":
        if len(error_history) != 0:
            if error_history[-1][1] != status["Error"]:
                print("Add: new value")
                to_add = True
            elif time.time()-error_history[-1][0] >= 60:
                print("Add with {} seconds!".format(time.time()-error_history[-1][0]))
                to_add = True
        else:
            print("Add: first elem")
            to_add = True

        if to_add:
            error_history.append([time.time(), status['Error']])
    status["Error"] = "No error"
            
        # convert timestamp to readable with: time.gmtime(1681401590.5839448)    
        # error_history.append([datetime.now().strftime("%d/%m/%Y %H:%M:%S"), status['Error']])

########### TKINTER ####################
'''
import tkinter as tk

# Update the values
def update_values():
    global status
    values[0].set("Temperature: {}".format(status["Temperature"]))
    values[1].set("PLL: {}".format(status["PLL"]))
    values[2].set("Current: {}".format(status["Current"]))
    values[3].set("Voltage: {}".format(status["Voltage"]))
    values[4].set("Reflected Power: {}".format(status["Reflected Power"]))
    values[5].set("Forward Power: {}".format(status["Forward Power"]))
    values[6].set("PWM: {}".format(status["PWM"]))
    values[7].set("On Off: {}".format(status["On Off"]))
    values[8].set("Enable foldback: {}".format(status["Enable foldback"]))
    values[9].set("Foldback in: {}".format(status["Foldback in"]))
    values[10].set("Error: {}".format(status["Error"]))

# Function to update the values automatically every second
def auto_update():
    update_values()
    root.after(1000, auto_update)  # Schedule the next update after 1000ms (1 second)


# Create the main Tkinter window
root = tk.Tk()
root.title("Value Display")
root.geometry("300x300")
# Create a list to hold the values
values = []
for i in range(11):
    values.append(tk.StringVar())  # Use StringVar to store the values as strings

# Create 10 labels to display the values
labels = []
for i in range(11):
    label = tk.Label(root, textvariable=values[i], compound='left')
    label.pack()
    labels.append(label)


# Start the automatic updates
auto_update()

# Start the Tkinter event loop
root.mainloop()

'''

# Main ########################################################################
print("Start RF generator...")
ser = srw.connect_serial("COM11")

status = {"Temperature":"ND","PLL":"ND","Current":"ND","Voltage":"ND","Reflected Power":"ND", 
          "Forward Power":"ND", "PWM":"ND", "On Off":"ND", "Enable foldback":"ND", "Foldback in":"ND", "Error":"No error"}



# Read parameters from csv file
duration, freq_list, power_list, error, msg = rcsv.read_and_plot("D:\Downloads\Book2.rf.csv", True, False)

if not error:
    error_history = []
    
    # Initialize
    index = 0
    next_time = duration[0]
    freq = freq_list[0]
    power = power_list[0]
    
    srw.send_cmd_string(ser,"ON")
    srw.send_cmd_string(ser,"PWR", power)
    # srw.send_cmd_string(ser,"PWM", 300)  # By setting the PWM, the PWR is overwritten!
    srw.send_cmd_string(ser,"FREQ", freq)
    # srw.send_cmd_string(ser,"FLDBCK_ON") # By enabling foldback the power is limited
    # srw.send_cmd_string(ser,"FLDBCK_VAL", 5)
    srw.read_param(ser, status, "STATUS")
    
    # Start the main functions
    init_time = time.time()
    exit_flag = False
    signal.signal(signal.SIGINT, handler)
    # auto_update()
    while time.time()-init_time <= sum(duration) and not exit_flag:
        if time.time()-init_time >= next_time:
            index += 1
            if index < len(duration):
                next_time = next_time + duration[index]
                power = power_list[index]
                freq = freq_list[index]
            srw.send_cmd_string(ser,"PWR", power)
            srw.send_cmd_string(ser,"FREQ", freq)
            # srw.send_cmd_string(ser,"FLDBCK_ON")
            # srw.send_cmd_string(ser,"FLDBCK_VAL", 5)
    
        srw.read_param(ser, status, "STATUS") # The list can be useful to see the raw data
        srw.read_param(ser, status, "FLDBCK_READ") # The list can be useful to see the raw data
        save_error_log()
        # update_values()
        
    # Soft turn off
    print("\nStart soft shut down...")
    srw.send_cmd_string(ser,"OFF")
    srw.send_cmd_string(ser,"PWM", 0)
    srw.empty_buffer(ser, status, wait=1)
    print("\nRead status to confirm shutdown:")
    srw.read_param(ser, status, "STATUS")
    
# Close ports
ser.close()


'''
# # Create a thread for running the update_value_label function
update_thread = threading.Thread(target=main_things)
update_thread.start()
'''



