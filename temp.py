connect (give 
listen
send (12k limit)
recv (recieves one data packet < 12k)


def connectTCP(host, port):
    socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    return HNetSocketBasic(socket)

def listenTCP(interface, port, handleNewConnection):
    socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket.bind((host, port))
    socket.listen(5)
    def acceptor():
        conn, addr = self.socket.accept()
        handleNewConnection(HNetSocketBasic(conn))
        
    thread.start_new_thread(acceptor, ())


#Add better timeout stuff
class HNetSocketTCP:
    def __init__(self, socket):
        self.socket = socket
    
    def send(self, data):
        length = len(data)
        header = struct.pack("!L", length)
        self.socket.sendAll(header + data)
        
    def recvDataLen(s, length):
        recvData = []
        recvBytes = 0
        
        while recvBytes < length:
            data = s.recv(length - recvBytes)
            recvBytes += len(data)
            recvData.append(data)
        return "".join(recvData)
    
    def recv(s):
        length = struct.unpack('!L', self.recvDataLen(s, 4))
        return recvDataLen(s, length)
        
    def close(self):
        self.socket.close()

class HNetStream:
    def __init__(self, socket):
        self.socket = socket
        self.recvQueue = Queue()
        self.

    def send(self, data):

    def recv(self):
        return self.recvQueue.get(True)


class HNetSendWait:
    def __init__(self, socket):
        self.socket = socket
        self.seq = 1
        self.lock = Lock()

    def send(self, data):
        with self.lock()
            self.seq += 1
            if self.seq < 0:
                self.seq = 1
        header = struct.pack("!L", self.seq)
        self.send(header + data)
        
    def recv(s):
        seq = struct.unpack('!L', s[:4])
        class Packet:
            def respond(msg):
                self.socket.

            def data():
                return s4:]
            
        return Packet()
        
    def close(self):
        self.socket.close()

    

class HNetStream(HNetSocketBasic):

sendAndWait
makeStream()



Client:
mySocket = Thingy(host)
s = mySocket.makeStream("blah")
s.send(mydata)





Host:

obj, stream = mySocket.recv()
if obj:
    obj.respond(someData)
    
if stream:
    

if isStream(obj, s):
    s, = 
if obj.isStream:
    header = obj.recv()
    if header == "Chat":
        spawnNewChatWindow(ojb)
else:
    obj.data
    obj.respond()




mySocket.listenStream()







small data
big data

packets that must get there
packets that we don't care if they get there

needs responses





GameInfo: Done
Text: Done
Files: 
Authentication(LATER)

thing = recv()
thing.respond(asdfjjsdalf)