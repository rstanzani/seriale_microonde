# -*- coding: utf-8 -*-
"""
Created on Tue Jan  9 15:00:04 2024

@author: admin
"""

import plc_socket as plcsk
import zmq
import time

timestamp_plc_check = time.time()
plc_check_refresh = 1 # second

context, socket = plcsk.subscriber("5432", "1001")
# socket.setsockopt(zmq.LINGER, 100) 

# good = 0
# bad = 0
i = 0
while i < 1000:
    if time.time() >= timestamp_plc_check + plc_check_refresh:
        # context, socket = plcsk.subscriber("5432", "1001")

        try:
            string = socket.recv(zmq.NOBLOCK)
            print(string)
            # print(string)
            i += 1
            # good += 1
        except zmq.error.Again:
            print("Error Again" )
            time.sleep(0.1)
            # bad +=1
        except:
            print("Error" )
            time.sleep(0.1)
        # socket.close()
        timestamp_plc_check = time.time()
        # socket.recv(zmq.NOBLOCK)
        # socket.recv(zmq.NOBLOCK)
        # socket.recv(zmq.NOBLOCK)
        # socket.recv(zmq.NOBLOCK)
        # socket.recv(zmq.NOBLOCK)
        # socket.close()

        # print("Good vs bad: {} {}".format(good, bad) )


socket.close()

# TEST scrittura
topic_pub = 2002
context_pub, socket_pub = plcsk.publisher("5433", topic_pub)

rfstr = str(2) + " " + str(10)
print("Rfstr type is: {}".format(type(rfstr)))
try:
    socket_pub.send_string("{} {}".format(topic_pub, rfstr))
except:
    print("Not working")

print("Sending rf data: {}".format(rfstr))

