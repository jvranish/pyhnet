import socket
import pickle
import struct
from threading import Lock, Event, Thread
from Queue import Queue
import sys
import traceback
import errno
import select

#TODO pickle tracebacks
#TODO add some handling for connections that are terminated midstream
#TODO allow our sockets and stream to operate like a standard socket, or like a with statement object

def startNewThread(target, args = (), kwargs = {}):
    thread = Thread(target = target, args = args, kwargs = kwargs)
    thread.start()
    return thread


def connectTCP(host, port, maxAttempts = 3, timeout = 1.0):
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tries = 0
    clientSocket.settimeout(timeout)
    connectSuccess = False
    while not connectSuccess:
        try:
            clientSocket.connect((host, port))
            clientSocket.settimeout(0.0)
            clientSocket.setblocking(1)
            connectSuccess = True
        except socket.timeout:
            if tries < maxAttempts:
                tries += 1
            else:
                raise
    return HNetSocketTCP(clientSocket)
    

def listenTCP(addresses, handleNewConnection, timeout = 0.1):
    listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        for address in addresses: # (host, port)
            listenSocket.bind(address)
        listenSocket.listen(5)
        done = Event()
        def acceptor():
            try:
                listenSocket.settimeout(timeout)
                while not done.isSet():
                    try:
                        conn, addr = listenSocket.accept()
                        handleNewConnection(HNetSocketTCP(conn), addr)
                    except socket.timeout:
                        pass
            finally:
                listenSocket.close()
    except:
        listenSocket.close()
        raise
    thread = startNewThread(acceptor)
    def stopListening():
        done.set()
    thread.stopListening = stopListening
    thread.socket = listenSocket
    return thread

#TODO this might be a good idea, should I add other exceptions?
class ConnectionClosed(Exception):
    pass
#Add better timeout stuff
class HNetSocketTCP:
    def __init__(self, s): 
        # socket must support, send(), recv(), and close(),
        # where send and recv operate on single data packets 
        self.socket = s
        #TODO make some sort of test and set primative
        self.lock = Lock()
        self.closed = False
        #self.socket.settimeout(0.0)
        self.socket.setblocking(0)
        
    def __enter__(self):
        return self
        
    def __exit__(self, type, value, traceback):
        self.close()
    
    def send(self, data):
        length = len(data)
        header = struct.pack("!L", length)
        buffer = header + data
        while buffer:
            r, w, e = select.select([],[self.socket],[])
            sent = self.socket.send(buffer)
            buffer = buffer[sent:]
        
        #self.socket.sendall()
        
    def __recvDataLen(self, length):
        recvData = []
        recvBytes = 0
        #TODO add more error checking/retrying, perhaps compare to pyro code
        while recvBytes < length:
            r, w, e = select.select([self.socket],[],[])
            data = self.socket.recv(length - recvBytes)
            if not data: raise ConnectionClosed
            recvBytes += len(data)
            recvData.append(data)
        return "".join(recvData)
    
    def recv(self):
        while True:
            try:
                length, = struct.unpack('!L', self.__recvDataLen(4))
                data = self.__recvDataLen(length)
                if data == None: break
                yield data
            except ConnectionClosed:
                break
            except socket.error, (errnum, msg):
                if errnum == errno.EBADF:
                    break  # almost certainly socket was closed
                elif errnum == errno.ECONNRESET: # test shutdown
                    break
                else:
                    raise
                
        
    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                #self.socket.shutdown(socket.SHUT_RD) # test shutdown WR
                self.socket.close()



class HNetPickleStream:
    def __init__(self, stream):
        self.stream = stream
    def send(self, obj, responseTo = 0):
        self.stream.send(pickle.dumps(obj), responseTo)
    def sendAndWait(self, obj, responseTo = 0):
        return self.stream.sendAndWait(pickle.dumps(obj), responseTo)
    def recv(self):
        for msg in self.stream.recv():
            yield pickle.loads(msg)
    def close():
        self.stream.close()


#TODO unify packet and stream somehow (at least on the recieving end)
#  we can send msg, bigMsg, obj, proxy, stream, it'd be nice to recieve all those without special action
#  like
#
# for msg, aux in recv():  #TODO do I want to use a queue here? and a separate thread to manage the streams?
#    msg.obj()?, aux.proxy(), .stream(), .bigMsgGetter()
#    
#   the msg vs pickled obj should be handled by a wrapper as you shouldn't mix a pickled object and regular msgs
#   proxy and stream and bigMsgGetter should be in aux
# 
#TODO unify our many send methods (send, sendAndWait, sendObj, sendObjAndWait into one)
#  send, sendFast, sendAndWait
# TODO put a timeout option on the sendAndWait somehow
# TODO check streamid negative numbers
def newStream(startMsg, sendWaitSocket, streamId, recvQueue, ourStream):
    streamMap = { True : -1 , False : -2 } #TODO improve this, probably replace with constant, and pass in
    class HNetStream: # can only use with HNetSendWait
        def __init__(self):
            self.closed = False
        def __del__(self):
            self.close()
        def send(self, msg):
            sendWaitSocket._send(streamId, msg, streamMap[ourStream])
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
                    sendWaitSocket._send(0, "", streamId) #send stream terminator
                else:
                    sendWaitSocket._send(0, "", -streamId) #send stream terminator            
        def msg(self):
            return startMsg
        
    return HNetStream()

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
        def dummyRead():
            for packet in stream.recv():
                pass
        startNewThread(dummyRead)
    def __getattr__(self, name):
      def messageSender(*args, **kwargs):
        response = self.stream.sendObjAndWait((name, args, kwargs))
        e, result = response.obj()
        if e == None:
          return result
        else:
          eClass, eArgs, tbMsg = e
          class HNetRemoteException(eClass):
              def __init__(self, *args, **kwargs):
                  eClass.__init__(self, *args, **kwargs)
              def __str__(self):
                  return eClass.__str__(self) + "\n" + tbMsg
          raise HNetRemoteException, eArgs 
      return messageSender

# add try...except for socket exceptions
# what happens if queues fill?

#
# acceptable interface for stream provides: send(), recv(), and close()
#  recv is a generator
#  close must terminate the recv generator 
#
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
        
    def _send(self, messageId, msg, responseTo = 0):
        header = struct.pack("!ll", messageId, responseTo)
        self.stream.send(header + msg)
        
    def __nextMessageId(self):
        with self.lock:
            self.messageId += 1
            if self.messageId < 1 or self.messageId > 2147483646: #python integers don't rollover
                self.messageId = 1
            return self.messageId
            
    def __nextStreamId(self):
        with self.lock:
            self.streamId -= 1
            if self.streamId > -1 or self.streamId < -2147483646:
                self.streamId = -1
            return self.streamId

    def send(self, msg, responseTo = 0):
        self._send(self.__nextMessageId(), msg, responseTo)
    
    def sendAndWait(self, msg, responseTo = 0):
        messageId = self.__nextMessageId()
        self.waiters[messageId] = Queue()
        self._send(messageId, msg, responseTo)
        resp = self.waiters[messageId].get(True)
        del self.waiters[messageId]
        return resp
    
    def sendAndStream(self, msg, responseTo = 0):
        streamId = self.__nextStreamId()
        queue = Queue()
        self.waiters[streamId] = queue
        self._send(streamId, msg, responseTo)
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
    
    def sendObjAndWait(self, obj, responseTo = 0):
        return self.sendAndWait(pickle.dumps(obj), responseTo)
    
    def sendProxy(self, obj, msg = "", responseTo = 0):
        stream = HNetSendWait(self.sendAndStream(msg, responseTo))
        def handleProxyStream():
            for packet in stream.recv():
                name, args, kwargs = packet.obj()
                try:
                    if name in [x for x in obj.__class__.__dict__.keys() if x[0] != "_"]:
                        packet.respondObj( (None, getattr(obj, name)(*args, **kwargs)) )
                except Exception,x:
                    packet.respondObj( ((sys.exc_info()[0], sys.exc_info()[1].args,  ''.join(traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback))), None) )
        
        startNewThread(handleProxyStream)
      
    def recv(self):
        for data in self.stream.recv():
            messageId, responseTo = struct.unpack('!ll', data[:8])
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
                if messageId in self.waiters:
                    self.waiters[messageId].put(msg)
                    
            elif messageId > 0 and responseTo > 0:  # response packet
                if responseTo in self.waiters:
                    self.waiters[responseTo].put(Packet())
                    
            elif messageId < 0 and responseTo >= 0:  # start of stream packet (might also be a response)
                queue = Queue()
                self.theirStreams[messageId] = queue
                stream = newStream(msg, self, messageId, queue, False)
                if responseTo == 0:
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
                    
            elif messageId == 0 and responseTo == 0:  # close socket # TODO maybe remove this
                break
                
            else:  # meaningless packet, ignore
                pass

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                #self._send(0,"",0) #test shutdown
                self.stream.close()
            
            
            
            
