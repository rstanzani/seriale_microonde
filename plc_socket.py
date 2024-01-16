# -*- coding: utf-8 -*-
"""
Created on Fri Oct 13 14:05:05 2023

@author: ronny
"""

import zmq


def publisher(port = "5432", topic = 1001):

    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:%s" % port)
    print(f"Starting socket with port {port} and topic {topic}")

    return context, socket


def subscriber(port = "5432", topicfilter = "1001"):
    '''For the conflate parameter, check: 
    https://stackoverflow.com/questions/48278859/how-to-have-limited-zmq-zeromq-pyzmq-queue-buffer-size-in-python'''
    
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.CONFLATE, 1)  # last msg only.  # try, TO PUT BEFORE THE CONNECT!!!! 
    socket.connect("tcp://localhost:%s" % port)
    socket.setsockopt_string(zmq.SUBSCRIBE, topicfilter)
    print(f"Open subscriber socket with port {port} and topic {topicfilter}")

    return context, socket
