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

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://localhost:%s" % port)
    socket.setsockopt_string(zmq.SUBSCRIBE, topicfilter)
    print(f"Open subscriber socket with port {port} and topic {topicfilter}")

    return context, socket
