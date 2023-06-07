import httplib2, base64, json, time
URL = "http://192.168.200.1/"
APIKEY = "0641cbefbfb63378999e572968c7259519b6457b12a797b7b3415079eed4b7eb248373c7bd914e80"

def request(pTarget):
    header = {'Authorization': "Bearer %s" % APIKEY}
    h = httplib2.Http()
    resp = ''
    content = ''
    try:
        resp, content = h.request(URL+pTarget, method="GET", headers=header)
    except:
        print("No response from server")
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
    data = json.loads(content)
    operands = data['OPERANDS']
    singleop = operands['{}SINGLE'.format(letter)]
    parameters = singleop[0]
    index = parameters['INDEX']
    value = parameters['V']
    return value

def is_plc_on_air():
    resp, content = getOp("M","40") #TODO set to M04 for working version
    time.sleep(.5)
    value = 0
    if content:
        value = get_val(content)
    return value

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


