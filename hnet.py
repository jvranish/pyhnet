import socket
import pickle
import struct
from threading import Lock, Event, Thread
import sys

def startNewThread(target):
    thread = Thread(target = target)
    thread.start()
    return thread

# TODO add multiple connect attempts?
def connectTCP(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    return HNetSocketTCP(s)

def listenTCP(addresses, handleNewConnection):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for address in addresses: # (host, port)
        s.bind(address)
    s.listen(5)
    done = Event()
    def acceptor():
        while not done.isSet():
            conn, addr = s.accept()
            handleNewConnection(HNetSocketTCP(conn), addr)
    thread = startNewThread(acceptor)
    def stopListening():
        done.set()
    return (thread, stopListening)

#Add better timeout stuff
class HNetSocketTCP:
    def __init__(self, s): 
        # socket must support, send(), recv(), and close(),
        # where send and recv operate on single data packets 
        self.socket = s
    
    def send(self, data):
        length = len(data)
        header = struct.pack("!L", length)
        self.socket.sendall(header + data)
        
    def __recvDataLen(self, length):
        recvData = []
        recvBytes = 0
        
        while recvBytes < length:
            data = self.socket.recv(length - recvBytes)
            if not data: return None
            recvBytes += len(data)
            recvData.append(data)
        return "".join(recvData)
    
    def recv(self):
        while True:
            packedLength = self.__recvDataLen(4)
            if packedLength == None: break
            length, = struct.unpack('!L', packedLength)
            data = self.__recvDataLen(length)
            if data == None: break
            yield data
        
    def close(self):
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()


# TODO check streamid negative numbers
#   need to mark a stream with owner
def newStream(startMsg, sendWaitSocket, streamId, recvQueue, ourStream):
    streamMap = { False : -1 , True : -2 } #TODO improve this
    class HNetStream: # can only use with HNetSendWait
        def __init__(self):
            self.closed = False
        def __del__(self):
            self.close()
        def send(self, msg):
            sendWaitSocket.send(streamId, msg, streamMap[ourStream])
        def recv(self):
            while True:
                msg = recvQueue.get(True)
                if msg == None: break
                yield msg
        def close():
            if not self.closed:
                self.closed = True
                recvQueue.put(None)
                if ourStream:
                    sendWaitSocket.__send(0, "", streamId) #send stream terminator
                else:
                    sendWaitSocket.__send(0, "", -streamId) #send stream terminator            
        def msg(self):
            return startMsg
        
    return Stream()

def getProxy(stream):
    return HNetProxy(HNetSendWait(stream))

def getBigMsg(stream):
    data = ""
    for chunk in stream.recv():
        data += chunk
    return data

class HNetProxy:
    def __init__(self, stream):
        self.stream = stream
    def __getattr__(self, name):
      def messageSender(*args, **kwargs):
        e, result = self.stream.sendObjAndWait((name, args, kwargs))
        if e == None:
          return result
        else:
          raise e
      return messageSender

# add try...except for socket exceptions
# what happens if queues fill?
class HNetSendWait:
    def __init__(self, stream):
        self.stream = stream
        self.messageId = 0 # we should never have a message 0
        self.lock = Lock()
        self.waiters = {}
        self.theirStreams = {}
        self.streamId = 0 # we should never have a stream 0
        self.closed = False
    def __del__(self):
        self.close()
        
    def __send(self, messageId, msg, responseTo = 0):
        header = struct.pack("!LL", messageId, responseTo)
        self.stream.send(header + msg)
        
    def __nextMessageId(self):
        with self.lock():
            self.messageId += 1
            if self.messageId < 1 or self.messageId > 2147483646: #python integers don't rollover
                self.messageId = 1
            return self.messageId
            
    def __nextStreamId(self):
        with self.lock():
            self.streamId -= 1
            if self.streamId > -1 or self.streamId < -2147483646:
                self.streamId = -1
            return self.streamId

    def send(self, msg, responseTo = 0):
        self.__send(self.__nextMessageId(), msg, responseTo)
    
    def sendAndWait(self, msg, responseTo = 0):
        messageId = self.__nextMessageId()
        self.waiter[messageId] = Queue()
        self.__send(messageId, msg, responseTo)
        resp = self.waiter[messageId].get(True)
        del self.waiter[messageId]
        return resp
    
    def sendAndStream(self, msg, responseTo = 0):
        streamId = self.__nextStreamId()
        queue = Queue()
        self.waiter[streamId] = queue
        self.__send(streamId, msg, responseTo)
        return newStream(None, self, streamId, queue, True)
        
    def sendBigMsg(self, msg, bigMsg, responseTo = 0):
        stream = self.sendAndStream(msg, responseTo)
        while len(bigMsg) > 12000:
            stream.send(bigMsg[:1200])
            bigMsg = bigMsg[1200:]
        stream.send(bigMsg)
        stream.close()
            

        
    
    def sendObj(self, obj, responseTo = 0):
        self.send(pickle.dumps(obj), responseTo)
    
    def sendObjAndWait():
        self.sendAndWait(pickle.dumps(obj), responseTo)
    
    def sendProxy(self, obj, msg, responseTo = 0):
        stream = HNetSendWait(self.sendAndStream(msg, responseTo))
        def handleProxyStream():
            for packet in stream.recv():
                name, args, kwargs = packet.obj()
                try:
                    if name in [x for x in obj.__class__.__dict__.keys() if x[0] != "_"]:
                        packet.respondObj( (None, getattr(obj, name)(*args, **kwargs)) )
                except:
                    packet.respondObj( (sys.exc_info()[1], None) )
        
        thread.start_new_thread(handleProxyStream, ())
      
    def recv(self):
        for data in self.socket.recv():
            messageId, responseTo = struct.unpack('!LL', data[:8])
            msg = data[8:]
            class Packet:
                def respond(_, msg):
                    self.send(msg, responseTo = messageId)
                def respondObj(_, obj):
                    self.sendObj(obj, responseTo = messageId)
                def respondAndWait(_, msg):
                    return self.sendAndWait(msg, responseTo = messageId)
                def respondObjAndWait(_, obj):
                    return self.sendObjAndWait(obj, responseTo = messageId)
                def msg(_):
                    return msg
                def obj(_):
                    return pickle.loads(msg)
                    
            if messageId > 0 and responseTo == 0:  # normal packet
                yield Packet()
                
            elif messageId < 0 and responseTo == -1:  #packet on one of their streams,
                if messageId in self.theirStreams:
                    self.theirStreams[messageId].put(msg)
                    
            elif messageId < 0 and responseTo == -2:  #packet on one of our streams,
                if responseTo in self.waiters:
                    self.waiters[messageId].put(msg)
                    
            elif messageId > 0 and responseTo > 0:  # response packet
                if responseTo in self.waiters:
                    self.waiters[responseTo].put(msg)
                    
            elif messageId < 0 and responseTo >= 0:  # start of stream packet (might also be a response)
                queue = Queue()
                self.theirStreams[messageId] = queue
                stream = newStream(msg, self, messageId, queue, False)
                if response == 0:
                    yield stream
                else:
                    self.waiters[messageId].put(stream)
                
            elif messageId == 0 and responseTo > 0:  # close their stream
                if responseTo in self.theirStreams:
                    self.theirStreams[-responseTo].put(None)
                    del self.theirStreams[-responseTo]
                    
            elif messageId == 0 and responseTo < 0:  # close our stream
                if responseTo in self.waiters:
                    self.waiters[responseTo].put(None)
                    del self.waiters[responseTo]
                    
            elif messageId == 0 and responseTo == 0:  # close socket
                self.__send(0,"",0)
                break
                
            else:  # meaningless packet, ignore
                pass

    def close(self):
        if not self.closed:
            self.closed = True
            self.__send(0,"",0)
            self.socket.close()
            
            
