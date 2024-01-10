# -*- coding: utf-8 -*-
"""
Created on Tue Jan  9 15:00:04 2024

@author: admin
"""

import plc_socket as plcsk
import zmq
import time

timestamp_plc_check = time.time()
plc_check_refresh = 0.8 # second

context, socket = plcsk.subscriber("5432", "1001")

good = 0
bad = 0
i = 0
while i < 1000:
    if time.time() >= timestamp_plc_check + plc_check_refresh:

        try:
            string = socket.recv(zmq.NOBLOCK)
            # print(string)
            i += 1
            good += 1
        except zmq.error.Again:
            time.sleep(2)
            print("Error Again" )
            bad +=1
        timestamp_plc_check = time.time()
        print("Good vs bad: {} {}".format(good, bad) )

