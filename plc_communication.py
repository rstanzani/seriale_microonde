# https://www.eaton.com/flash/eaton/json-api/Content/01_allgemeines/12_Get_started.htm

import httplib2, base64, json, time
URL = "http://10.235.2.149/"
APIKEY = "374fdc08c68e01fbc3836bd84fe5120f0ddb3613ed132979a1802449b3490af61ecc630025eb3ad5"

def request(pTarget):
    header = {'Authorization': "Bearer %s" % APIKEY}
    h= httplib2.Http()
    resp, content = h.request(URL+pTarget, method="GET",headers=header)
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

def main():
    if(not isRunning()):
        resp, content = request("api/set/op=state&v1=RUN")
        time. sleep(.300)
    resp, content = setOp("M",11,1)
main()
