import socket
import pickle
import struct
from threading import Lock, Event, Thread
from Queue import Queue
import sys
import traceback
import errno

#TODO make it possible to reply to streams (not too bad)
#TODO add UDP sockets and some nice highlevel abstractions over them 
#     (send, send and make sure it gets there, send and make sure it gets there in order, proper throttling)
#TODO make some simple wrappers for other common socket functions (so that people won't usually have to import socket)
#TODO add support for alternate thread libraries
#TODO add log entries?
#TODO consider queue fill exceptions (perhaps put timeouts on puts?)
#TODO figure out a way to kill threads (or throw exceptions to threads), and then make the proxy computations timeout
#TODO make a wrapper for dumps/loads that throws MetadataError instead of whatever it currently does

def startNewThread(target, args = (), kwargs = {}):
    thread = Thread(target = target, args = args, kwargs = kwargs)
    thread.start()
    return thread

    
ERRNO_RETRIES=[errno.EINTR, errno.EAGAIN, errno.EWOULDBLOCK]
if hasattr(errno, "WSAEINTR"):
    ERRNO_RETRIES.append(errno.WSAEINTR)
if hasattr(errno, "WSAEWOULDBLOCK"):
    ERRNO_RETRIES.append(errno.WSAEWOULDBLOCK)

ERRNO_BADF=[errno.EBADF]
if hasattr(errno, "WSAEBADF"):
    ERRNO_BADF.append(errno.WSAEBADF)
    
def retryable(e):
    err=getattr(e,"errno",e.args[0])
    return err in ERRNO_RETRIES
        
def isBadSocket(e):
    err=getattr(e,"errno",e.args[0])
    return err in ERRNO_BADF or err == errno.ECONNRESET
    
class ConnectionError(Exception): pass
class ConnectFailed(ConnectionError): pass
class ConnectionClosed(ConnectionError): pass
class ConnectionTimedOut(ConnectionError): pass
class UnknownServerError(ConnectionError): pass
class HostInvalid(ConnectionError): pass
class ServerStartFail(ConnectionError): pass

def HighLevelTCPSocket(s): return HNetPickleStream(HNetSendWait(TCPPacketSocket(s)))
def TCPPacketSocket(s): return HNetPacketize(HNetTCPSocket(s))

def connectTCP(host, port, maxAttempts = 3, timeout = 1.0, socketWrapper = HighLevelTCPSocket):
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tries = 0
    connectSuccess = False
    while not connectSuccess:
        try:
            clientSocket.settimeout(timeout)
            clientSocket.connect((host, port))
            clientSocket.settimeout(0.0)
            clientSocket.setblocking(1)
            connectSuccess = True
        except socket.timeout:
            if tries < maxAttempts:
                tries += 1
            else:
                raise ConnectionTimedOut
        except socket.gaierror, e:
            raise HostInvalid, e
        except socket.error, e:
            raise ConnectFailed, e
        
    return socketWrapper(clientSocket)
    
class HNetTCPServer:
    def __init__(self, addresses, newConnectionHandler, timeout = 0.01, reuseaddr=True, keepalive=True, socketWrapper = HighLevelTCPSocket):
        self.stopped = True
        self.lock = Lock()
        self.socket = None
        self.timeout = timeout
        self.addresses = addresses
        self.handler = newConnectionHandler
        self.thread = None
        self.socketWrapper = socketWrapper
        self.reuseaddr = reuseaddr
        self.keepalive = keepalive
        
    def __enter__(self): 
        self.start()
        return self
    def __exit__(self, type, value, traceback): self.stop()
    
    def start(self):
        if self.stopped:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.stopped = False
                if self.reuseaddr:
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if self.keepalive:
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                self.socket.settimeout(self.timeout)
                for address in self.addresses: # (host, port)
                    self.socket.bind(address)
                self.socket.listen(5)
            except socket.gaierror, e:
                raise HostInvalid, e
            except socket.error, e:
                raise ServerStartFail, e
            except:
                self.stop()
                raise
            self.thread = startNewThread(self.__acceptor)
                def __acceptor(self):
        try:
            while not self.stopped:
                try:
                    conn, addr = self.socket.accept()
                    startNewThread(self.handler, (self.socketWrapper(conn), addr))
                except socket.timeout:
                    pass
                except socket.error, e:
                    if not self.stopped:
                        raise UnknownServerError,  e
        finally:
            self.stop()
            self.socket = None
        
    def stop(self):
        with self.lock:
            if not self.stopped:
                self.stopped = True
                self.socket.close()


class StreamInterface:
    def __init__(self):
        self.lock = Lock()
        self.closed = False
        
    def __enter__(self): return self
    def __exit__(self, type, value, traceback): self.close()
    def __del__(self): self.close()
    def send(self, *args, **kwargs): raise NotImplementedError, "send needs to be implemented in your superclass"
    def recv(self, *args, **kwargs): raise NotImplementedError, "recv needs to be implemented in your superclass"
        
    def recvs(self, *args, **kwargs):
        while True:
            data = self.recv(*args, **kwargs)
            if not data: break
            yield data
        self.close()
            
    def onClose(self): pass
    
    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                self.onClose()
                 
class StreamWrapperInterface(StreamInterface):
    def __init__(self, stream):
        self.onInit(stream)
        StreamInterface.__init__(self)
        self.stream = stream
        
    def onInit(self, stream): pass
        
    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                self.onClose()
                self.stream.close()
                
class ByteStreamInterface(StreamInterface): pass
class PacketStreamInterface(StreamInterface): pass
class ObjectStreamInterface(StreamWrapperInterface): pass    
                

class HNetTCPSocket(ByteStreamInterface):
    def __init__(self, s):
        ByteStreamInterface.__init__(self)
        self.socket = s
        self.socket.settimeout(0.0)
        self.socket.setblocking(1)
        
    def send(self, data):
        try:
            self.socket.sendall(data)
        except socket.timeout:
            raise ConnectionTimedOut
        except socket.error, e:
            raise ConnectionClosed, e
            
    def recv(self, maxRead = 4096):
        while True:
            try:
                return self.socket.recv(maxRead)
            except socket.timeout:
                raise ConnectionTimedOut
            except socket.error, e:
                if retryable(e):
                    time.sleep(0.00001)
                    continue
                else:
                    return None
                    # connection was probably closed
                    # it's hard to tell if this is an error, or if the other side just did a shutdown
                    #   if you get a shutdown right in the middle of a recv you can get a different kind of error
                    #   than if you do a shutdown before
                    #   and of course the errors/bahaviors are all different in different platforms 

    def onClose(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except:
            pass #TODO maybe add logging here?



class HNetPacketize(PacketStreamInterface):
    def __init__(self, stream):
        self.stream = stream
        if not isinstance(stream, ByteStreamInterface): raise Exception, "HNetPacketize can only wrap byte streams"
        PacketStreamInterface.__init__(self)

    def onClose(self):
        self.stream.close()
        
    def send(self, data):
        self.stream.send(struct.pack("!L", len(data)) + data)
        
    def __recvDataLen(self, length):
        recvData = []
        recvBytes = 0
        while recvBytes < length:
            data = self.stream.recv(length - recvBytes)
            if not data: raise ConnectionClosed
            recvBytes += len(data)
            recvData.append(data)
        return "".join(recvData)
        
    def recv(self):
        try:
            length, = struct.unpack('!L', self.__recvDataLen(4))
            return self.__recvDataLen(length)
        except ConnectionClosed:
            return None


class StreamError(Exception): pass
class StreamClosedBeforeReply(StreamError): pass
class StreamErrorBadMetadata(StreamError): pass

NotReply = 0
StreamPacket = -1
CloseStream = -2

def newStream(sendWaitSocket, streamId, recvQueue):
    class HNetStream(PacketStreamInterface): # can only use with HNetSendWait
        def send(self, msg): sendWaitSocket._send(streamId, msg, StreamPacket)
        def recv(self): return recvQueue.get(True)
        def onClose(self):
            recvQueue.put(None)
            try:
                sendWaitSocket._send(streamId, "", CloseStream) #send stream terminator
            except:
                pass
    sendWaitSocket.streamsFinished.clear()
    return HNetStream()

def newPacket(data, messageId, parentSocket, stream):
    class Packet:
        def reply(_, msg):
            if messageId < 0: raise Exception("You cannot reply to a stream")
            parentSocket.send(msg, replyTo = messageId)
        def replyAndWait(_, msg):
            if messageId < 0: raise Exception("You cannot reply to a stream")
            return parentSocket.sendAndWait(msg, replyTo = messageId)
        def replyWithProxy(_, obj, msg = ''):
            if messageId < 0: raise Exception("You cannot reply to a stream")
            return parentSocket.sendProxy(obj, msg, replyTo = messageId)
        def replyWithBigMsg(_, bigMsg, msg = ''):
            if messageId < 0: raise Exception("You cannot reply to a stream")
            return parentSocket.sendBigMsg(bigMsg, msg, replyTo = messageId)
        def replyWithStream(_, msg = ''):
            if messageId < 0: raise Exception("You cannot reply to a stream")
            return parentSocket.sendStream(msg, replyTo = messageId)
        def msg(_):
            return data
        def _messageId(_):
            return messageId
        def _stream(_):
            return stream
        def proxy(_):
            if stream:
                return HNetProxy(HNetPickleStream(HNetSendWait(stream)))
            else:
                raise Exception("Tried to create proxy on a non-stream object.\nYou were probably expecting a stream but the other side sent a regular message.")
        def bigMsg(_):
            if stream:
                recvData = ""
                for chunk in stream.recvs():
                    recvData += chunk
                return recvData
            else:
                raise Exception("Tried to create recv bigMsg on a non-stream object.\nYou were probably expecting a stream but the other side sent a regular message.")
    return Packet()


#  wraps a HNetSendWait stream 
#   converts packets to pickled python object packets
#   note that streams and bigMsgs still work with strings of bytes
class HNetPickleStream(ObjectStreamInterface):
    def onInit(self, stream):
        if not isinstance(stream, HNetSendWait): raise Exception, "HNetPickleStream can only wrap HNetSendWait (or derivatives)"
    def send(self, obj, replyTo = NotReply):
        self.stream.send(pickle.dumps(obj), replyTo)
    def sendAndWait(self, obj, replyTo = NotReply):
        packet = self.stream.sendAndWait(pickle.dumps(obj), replyTo)
        return newPacket(pickle.loads(packet.msg()), packet._messageId(), self, packet._stream())
    def recv(self):
        packet = self.stream.recv()
        return packet and newPacket(pickle.loads(packet.msg()), packet._messageId(), self, packet._stream())
        
    def sendStream(self, obj, replyTo = NotReply):
        return self.stream.sendStream(pickle.dumps(obj), replyTo)
        
    def sendBigMsg(self, bigMsg, obj, replyTo = NotReply):
        self.stream.sendBigMsg(bigMsg, pickle.dumps(obj), replyTo)
         
    def sendProxy(self, obj, objMsg = None, replyTo = NotReply):
        self.stream.sendProxy(obj, pickle.dumps(objMsg), replyTo)
        
    def waitForStreams(self, timeout = None):
        self.stream.waitForStreams(timeout)

class HNetProxy:
    def __init__(self, stream):
        self.stream = stream
        def dummyRead():
            for _ in stream.recvs():
                pass
        startNewThread(dummyRead)
    def __del__(self):
        self.stream.close()
    def __getattr__(self, name):
      def messageSender(*args, **kwargs):
        packet = self.stream.sendAndWait((name, args, kwargs))
        (e, result) = packet.msg()
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

class Counter:
    def __init__(self, intialValue = 0):
        self.initialValue = intialValue - 1 # -1 cause we'll increment before fist return
        self.value = self.initialValue 
        self.lock = Lock()
        
    def __call__(self):
        with self.lock:
            self.value += 1
            if self.value > 2147483646: #python integers don't rollover
                self.value = self.initialValue
            return self.value

class HNetSendWait(ObjectStreamInterface):
    def __init__(self, stream):
        if not isinstance(stream, PacketStreamInterface): raise Exception, "HNetSendWait can only wrap packet streams"
        ObjectStreamInterface.__init__(self, stream)
        self.nextMessageId = Counter(1) # we should never have a message 0
        self.waiters = {}
        self.streams = {} # negative streams are ours, positive theirs
        self.nextStreamId = Counter(1) # we should never have a stream 0
        self.recvQueue = Queue()
        startNewThread(self.recvThread)
        self.streamsFinished = Event()
        self.streamsFinished.set()
        
    def _send(self, messageId, msg, replyTo = NotReply):
        header = struct.pack("!ll", messageId, replyTo)
        self.stream.send(header + msg)

    def send(self, msg, replyTo = NotReply):
        self._send(self.nextMessageId(), msg, replyTo)
    
    def sendAndWait(self, msg, replyTo = NotReply, timeout = None):
        messageId = self.nextMessageId()
        self.waiters[messageId] = Queue()
        self._send(messageId, msg, replyTo)
        resp = self.waiters[messageId].get(True, timeout)
        if resp == None:
            raise StreamClosedBeforeReply
        del self.waiters[messageId]
        return resp
    
    def sendStream(self, msg, replyTo = NotReply):
        streamId = -self.nextStreamId()
        queue = Queue()
        self.streams[streamId] = queue
        self._send(streamId, msg, replyTo)
        return newStream(self, -streamId, queue)
        
    def sendBigMsg(self, bigMsg, msg = '', replyTo = NotReply):
        stream = self.sendStream(msg, replyTo)
        while len(bigMsg) > 12000:
            stream.send(bigMsg[:1200])
            bigMsg = bigMsg[1200:]
        stream.send(bigMsg)
        stream.close()
    
    def sendProxy(self, obj, msg = '', replyTo = NotReply):
        stream = HNetPickleStream(HNetSendWait(self.sendStream(msg, replyTo)))
        def handleProxyStream():
            for packet in stream.recvs():
                name, args, kwargs = packet.msg()
                try:
                    if name in [x for x in obj.__class__.__dict__.keys() if x[0] != "_"]:
                        packet.reply( (None, getattr(obj, name)(*args, **kwargs)) )
                except Exception,x:
                    packet.reply( ((sys.exc_info()[0], sys.exc_info()[1].args,  ''.join(traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback))), None) )
        startNewThread(handleProxyStream)
      
    def recvThread(self):
        while True:
            data = self.stream.recv()
            if not data: 
              self.recvQueue.put(None)
              break
            if len(data) < 8: raise StreamErrorBadData
            messageId, replyTo = struct.unpack('!ll', data[:8])
            msg = data[8:]

            if replyTo >= 0: # normal packet, reply, or start of stream
                if messageId > 0: # normal packet
                    packet = newPacket(msg, messageId, self, None)
                elif messageId < 0: # start of stream #TODO cannot reply to sendStream
                    queue = Queue()
                    self.streams[-messageId] = queue
                    packet = newPacket(msg, messageId, self, newStream(self, messageId, queue))
                else: continue # should never happen
                if replyTo == NotReply:
                    self.recvQueue.put(packet)
                else:
                    self.waiters[replyTo].put(packet)
            else: # stream packet
                if replyTo == CloseStream:
                    with self.lock:
                        if messageId in self.streams:
                            self.streams[messageId].put(None)
                            del self.streams[messageId]
                            if len(self.streams) == 0:
                                self.streamsFinished.set()
                else:
                    if messageId in self.streams:
                        self.streams[messageId].put(msg)
        
    def recv(self):
        return self.recvQueue.get()
        
    def waitForStreams(self, timeout = None):
        self.streamsFinished.wait(timeout)
        
    def onClose(self):
        for q in self.waiters.values():
            q.put(None)
        self.waiters = {}
        for q in self.streams.values():
            q.put(None)
        self.streams = {}
        self.recvQueue.put(None)

