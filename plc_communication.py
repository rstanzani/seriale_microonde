import httplib2, base64, json, time
URL = "http://192.168.200.1/"
APIKEY = "0641cbefbfb63378999e572968c7259519b6457b12a797b7b3415079eed4b7eb248373c7bd914e80"

def request(pTarget):
    header = {'Authorization': "Bearer %s" % APIKEY}
    h = httplib2.Http(timeout = 2)
    resp = ''
    content = ''
    try:
        resp, content = h.request(URL+pTarget, method="GET", headers=header)
    except:
        print("PLC error: No response from server. Check the connection.")
    return resp, content

def isRunning():
    r = False
    resp, content = request("api/get/data?elm=STATE");
    try:
        o = json. loads(content);
        r = (o["SYSINFO"]["STATE"]) == "RUN"
    except ValueError:
        print ('JSON Decoding failed')
    return r

def setOp(pOp, pIndex, pVal):
    url = "api/set/op?op="+pOp+"&index="+str(pIndex)+"&val="+str(pVal)
    return request(url)

def getOp(letter="I",num=""):
    url = "api/get/data?elm={}({})".format(letter,num)
    return request(url)

def getState():
    url = "api/get/data?elm=STATE"
    return request(url)

def get_val(content, letter="M"):
    value = 0 # 0 = default value
    if content != "":
        data = json.loads(content)
        operands = data['OPERANDS']
        singleop = operands['{}SINGLE'.format(letter)]
        parameters = singleop[0]
        # index = parameters['INDEX']
        value = parameters['V']
    return value

def is_plc_on_air():
    resp, content = getOp("M","17")

    time.sleep(.3)
    value = 0
    if content != "":
        value = get_val(content)
    return value

plc_values = [["MB","11"],["MB","13"],["MB","110"],["MB","120"],["MB","130"],["MB","150"],["MB","70"],["MB","80"],["MB","140"],["MB","160"],["MW","20"],["MW","22"],["MW","24"],["MW","26"],["MW","28"],["MW","30"]]

def get_logger_values():
    global plc_values
    resp = [''] * len(plc_values)
    val = [0] * len(plc_values)
    resp[0] = getOp(plc_values[0][0], plc_values[0][1])[1]
    if resp[0] != "":    # use the first value as a connection check
        val[0] = get_val(resp[0], plc_values[0][0])
        for i in range(1, len(plc_values)):
            time.sleep(0.001)
            resp[i] = getOp(plc_values[i][0], plc_values[i][1])[1]
            val[i] = get_val(resp[i], plc_values[i][0])

    # In string format for the csv file
    strng = ""
    spaces_pos = [1, 5, 9, 11, 13]  # Index for empty column, as from requirements
    for i in range(0, len(val)):
        column_sign = ";;" if i in spaces_pos else ";"
        strng += str(val[i]) + column_sign


    return val, strng


# import time
# import zmq

# context = zmq.Context()
# # context = zmq.Context()
# socket = context.socket(zmq.REP)
# socket.bind("tcp://*:5555")

# def main():
#     counter = 0
#     # if(not isRunning()):
#     #     resp, content = request("api/set/op=state&v1=RUN")
#     #     time.sleep(.300)
#     # resp, content = getOp("Q","4")
#     while 1:
#        value = is_plc_on_air()
#        time.sleep(1)
#        # print("Value is {}".format(value))
#        # counter += 1

# resp, content = getOp("MB", "26") #counter
# print(get_val(content, "MB"))
# main()


