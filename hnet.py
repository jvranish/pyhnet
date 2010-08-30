import socket
import pickle
import struct

class blah:
    __init__(self):
        self.identCouter = 1
        self.messages = set()

    messageRegister(self, messageIdent):
        self.messages.add(messageIdent)
        
    messageRelease(self, messageIdent):
        self.messages.discard(messageIdent)

def sendWait (s, obj):
    sendDataWait(s, pickle.dumps(obj))

def sendDataWait (s, data)
    messageIdent = self.identCounter
    self.identCounter += 1
    if self.identCounter < 1:
        self.identCounter = 1
    length = len(data)
    header = struct.pack("!LL", messageIdent, length)
    cv = asdfasdf
    s.registerWaitFor(cv, messageIdent)
    s.sendall(header + data)
    
    with cv:
        cv.wait()
    data = s.waitData[messageIdent]
    del s.waitData[messageIdent]
    return data


def somewhereelse(cv):
    cv.notify()

def send(s, obj, messageIdent = 0):
    sendData(s, pickle.dumps(obj))

def sendData(s, data, messageIdent = 0):
    length = len(data)
    header = struct.pack("!LL", messageIdent, length)
    s.sendall(header + data)

def recvDataLen(s, length):
    recvData = []
    recvBytes = 0
    
    while recvBytes < length:
        data = s.recv(length - recvBytes)
        recvBytes += len(data)
        recvData.append(data)
    return "".join(recvData)

def recvData(s):
    (messageIdent, length) = struct.unpack('!LL', recvDataLen(s, 8))
    return (messageIdent, recvDataLen(s, length))
        
def recv(s):
    (data, messageIdent) = recvData(s)
    return (messageIdent, pickle.loads(data))


class HNetSocket:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.done = False

    def listen(self, host, port): # , acceptor = lambda x: True
        self.socket.bind((host, port))
        self.socket.listen(5)
        thread.start_new_thread(self.acceptConnections, ())

    def acceptConnections(self):
        while not self.done:
            conn, addr = self.socket.accept()
            self.accept(conn, addr)

    def accept(self, conn, addr):
        pass
        
    def connect(self, host, port):
        self.socket.connect((host, port))

    def close(self):
        self.done = True
        self.socket.close()

    def sendData(self, data, responseID = None):
      pass

    def send(self, obj, reponseID = None):
        send

    def sendAndWait(self, 

    def recv(self):
        responseID = something
        messageID = something
        data = stuff
        
        class Message:
            def __init__(msg, data):
                msg.data = data

            def reply(msg, data):
                self.sendResponse(responseID, data)

            def replyAndWait(msg, data):
                self.sendResponseAndWait(responseID, data)
                
       return Message(data)

