import httplib2, base64, json, time
URL = "http://192.168.200.1/"
APIKEY = "0641cbefbfb63378999e572968c7259519b6457b12a797b7b3415079eed4b7eb248373c7bd914e80"

# plc_values = [["MB","11"],["MB","13"],["MB","110"],["MB","120"],["MB","130"],["MB","150"],["MB","70"],["MB","80"],["MB","140"],["MB","160"],["MW","20"],["MW","22"],["MW","24"],["MW","26"],["MW","28"],["MW","30"]]
time_values = [["MW","20"],["MW","22"],["MW","24"],["MW","26"],["MW","28"],["MW","30"]]
values_to_average = [["MB","13"],["MB","15"],["MB","110"],["MB","120"],["MB","130"],["MB","150"],["MB","70"],["MB","80"],["MB","140"],["MB","170"]]

def Average(lst):
    avg = 0

    if len(lst) > 0:
        print("Avrg on {} values".format(len(lst)))
        avg = round(sum(lst) / len(lst), 1)
    return avg

class Cell_Data:
    MB11 = []
    MB13 = []
    MB110 = []
    MB120 = []
    MB130 = []
    MB150 = []
    MB70 = []
    MB80 = []
    MB140 = []
    MB160 = []

    def reset(self):
        self.MB11 = []
        self.MB13 = []
        self.MB110 = []
        self.MB120 = []
        self.MB130 = []
        self.MB150 = []
        self.MB70 = []
        self.MB80 = []
        self.MB140 = []
        self.MB160 = []

    def append_values(self, val):
        # print("Append these values: {}".format(val))
        self.MB11.append(val[0])
        self.MB13.append(val[1])
        self.MB110.append(val[2])
        self.MB120.append(val[3])
        self.MB130.append(val[4])
        self.MB150.append(val[5])
        self.MB70.append(val[6])
        self.MB80.append(val[7])
        self.MB140.append(val[8])
        self.MB160.append(val[9])
        # print("MB11 is now {}".format(self.MB11) )

    def get_average(self):
        return [Average(lst) for lst in [self.MB11,self.MB13,self.MB110,self.MB120,self.MB130,self.MB150,self.MB70,self.MB80,self.MB140,self.MB160]]


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

# def isRunning():
#     r = False
#     try:
#         resp, content = request("api/get/data?elm=STATE");
#     except:
#         print("PLC error: No response from server. Check the connection.")
#     try:
#         o = json. loads(content);
#         r = (o["SYSINFO"]["STATE"]) == "RUN"
#     except ValueError:
#         print ('JSON Decoding failed')
#     return r

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

def get_time_values():
    global time_values
    resp = [''] * len(time_values)
    val = [0] * len(time_values)
    resp[0] = getOp(time_values[0][0], time_values[0][1])[1]
    if resp[0] != "":    # use the first value as a connection check
        val[0] = get_val(resp[0], time_values[0][0])
        for i in range(1, len(time_values)):
            time.sleep(0.001)
            resp[i] = getOp(time_values[i][0], time_values[i][1])[1]
            val[i] = get_val(resp[i], time_values[i][0])
    return val

def get_values():
    noresp = True
    global values_to_average
    resp = [''] * len(values_to_average)
    val = [0] * len(values_to_average)
    resp[0] = getOp(values_to_average[0][0], values_to_average[0][1])[1]
    if resp[0] != "":    # use the first value as a connection check
        noresp = False
        val[0] = get_val(resp[0], values_to_average[0][0])
        for i in range(1, 10):
            time.sleep(0.001)
            resp[i] = getOp(values_to_average[i][0], values_to_average[i][1])[1]
            val[i] = get_val(resp[i], values_to_average[i][0])
    return noresp, val

def get_logger_values(cell_data):

    avrg_val = cell_data.get_average()
    time_val = get_time_values()
    val = avrg_val + time_val

    # In string format for the csv file
    strng = ""
    spaces_pos = [1, 5, 9, 11, 13]  # Index for empty column, as from requirements
    for i in range(0, len(val)):
        column_sign = ";;" if i in spaces_pos else ";"
        strng += str(val[i]) + column_sign
    return strng

