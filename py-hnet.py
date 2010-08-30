import socket
import pickle
import struct

def sendData(s, obj):
    data = pickle.dumps(obj)
    length = len(data)
    header = struct.pack("!L", length)
    s.sendall(header + data)

def _recvData(s, length):
    recvData = []
    recvBytes = 0
    
    while recvBytes < length:
        data = s.recv(length - recvBytes)
        recvBytes += len(data)
        recvData.append(data)
    return "".join(recvData)
        
def recvData(s):
    (length,) = struct.unpack('!L', _recvData(s, 4))
    return pickle.loads(_recvData(s, length))




