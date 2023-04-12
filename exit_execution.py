# -*- coding: utf-8 -*-
"""
Created on Wed Apr 12 09:29:46 2023

@author: ronny
"""

import signal
import time
import sys
# import readchar
 
stop = False

def handler(signum, frame):
    msg = "\n Ctrl-c was pressed. Do you really want to exit? y/n \n "
    print(msg, end="", flush=True)
    res = input()
    # res = readchar.readchar()
    if res == 'y':
        raise SystemExit("Exiting on user request")
        # sys.exit()
    else:
        print("", end="\r", flush=True)
        print(" " * len(msg), end="", flush=True) # clear the printed line
        print("    ", end="\r", flush=True)

 
 
signal.signal(signal.SIGINT, handler)
 
count = 0
while not stop:
    print(f"{count}", end="\r", flush=True)
    count += 1
    time.sleep(0.1)
    
    
    
    
    
    
    
    
    
import signal
import time
 
def handler(signum, frame):
    res = input("Ctrl-c was pressed. Do you really want to exit? y/n ")
    if res == 'y':
        exit(1)
 
signal.signal(signal.SIGINT, handler)
 
count = 0
while True:
    print(count)
    count += 1
    time.sleep(0.1)