import socket
import pickle
import struct
from threading import Lock, Event, Thread
from Queue import Queue
import sys
import traceback
import errno
import select


#TODO add support for alternate thread libraries
#TODO add log entries
# check - TODO pickle tracebacks
#TODO add some handling for connections that are terminated midstream
#    make group of exceptions thrown from connect, close, resv, send, listen
#    collect possible socket exceptions
#    also consider queue fill exceptions
#    if stream breaks we need to shutdown all the queues
#TODO allow our sockets and stream to operate like a standard socket, or like a with statement object
#TODO timeout cancel proxy computation (thread them, how to kill on fail?)
# TODO put a timeout option on the sendAndWait somehow


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
class ConnectFailed(Exception): pass
class ConnectionClosed(ConnectionError): pass
class ConnectionTimedOut(ConnectionError): pass
class UnknownConnectionError(ConnectionError): pass
class UnknownServerError(ConnectionError): pass
class HostInvalid(ConnectionError): pass
class ServerStartFail(ConnectionError): pass


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
                raise ConnectionTimedOut
        except socket.gaierror, e:
            raise HostInvalid, e
        except socket.error, e:
            raise ConnectFailed, e
        
    return HNetSocketTCP(clientSocket)
    
class HNetTCPServer:
    def __init__(self, addresses, newConnectionHandler, timeout = 0.1):
        self.stopped = True
        self.lock = Lock()
        self.socket = None
        self.timeout = timeout
        self.addresses = addresses
        self.handler = newConnectionHandler
        self.thread = None
    
    def start(self):
        if self.stopped:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.stopped = False
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
                    startNewThread(self.handler, (HNetSocketTCP(conn), addr))
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




class HNetSocketTCP:
    def __init__(self, s): 
        # socket must support, send(), recv(), and close(),
        # where send and recv operate on single data packets 
        self.socket = s
        self.lock = Lock()
        self.closed = False
        self.socket.settimeout(0.0)
        self.socket.setblocking(1)
        
    def __enter__(self):
        return self
        
    def __exit__(self, type, value, traceback):
        self.close()
    
    def send(self, data):
        length = len(data)
        header = struct.pack("!L", length)
        try:
            self.socket.sendall(header + data)
        except socket.timeout:
            raise ConnectionTimedOut
        except socket.error, e:
            raise ConnectionClosed, e
            
    def __recvDataLen(self, length):
        recvData = []
        recvBytes = 0
        while recvBytes < length:
            try:
                data = self.socket.recv(length - recvBytes)
                if not data: raise ConnectionClosed
                recvBytes += len(data)
                recvData.append(data)
            except socket.error, e:
                if retryable(e):
                    time.sleep(0.00001)
                    continue
                else:
                    raise
        return "".join(recvData)
    
    def recv(self):
        while True:
            try:
                length, = struct.unpack('!L', self.__recvDataLen(4))
                yield self.__recvDataLen(length)
            except ConnectionClosed:
                break
            except socket.timeout:
                raise ConnectionTimedOut
            except socket.error, e:
                break # connection was probably closed
                # it's hard to tell if this is an error, or if the other side just did a shutdown
                #   if you get a shutdown right in the middle of a recv you can get a different kind of error
                #   than if you do a shutdown before
                #   and of course the errors/bahaviors are all different in different platforms 
                
                #if isBadSocket(e):
                #    break  # almost certainly socket was closed
                #else:
                #    raise ConnectionClosed, e
                
        
    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                try:
                    self.socket.shutdown(socket.SHUT_RDWR) # test shutdown WR
                    self.socket.close()
                except:
                    pass #TODO maybe add logging here?


class StreamClosedBeforeReply(Exception): pass

#  wraps a packet stream 
#   converts byte packets to pickled python object packets
#   
#
class HNetPickleStream:
    def __init__(self, stream):
        self.stream = stream
    def send(self, obj, responseTo = 0):
        self.stream.send(pickle.dumps(obj), responseTo)
    def sendAndWait(self, obj, responseTo = 0):
        packet = self.stream.sendAndWait(pickle.dumps(obj), responseTo)
        return mkPacket(pickle.loads(packet.msg()), packet._messageId(), self, None)
    def recv(self):
        for packet in self.stream.recv():
            yield mkPacket(pickle.loads(packet.msg()), packet._messageId(), self, None)
    def close():
        self.stream.close()


OurStream = -1
TheirStream = -2
def newStream(startMsg, sendWaitSocket, streamId, recvQueue, streamSource):
    class HNetStream: # can only use with HNetSendWait
        def __init__(self):
            #TODO add locking here? perhaps put common close functionality in baseclass?
            self.closed = False
        def __del__(self):
            self.close()
        def send(self, msg):
            sendWaitSocket._send(streamId, msg, streamSource)
        def recv(self):
            while True:
                msg = recvQueue.get(True)
                #print 'recving data', msg
                
                if msg == None: break
                yield msg
        def close(self):
            if not self.closed:
                self.closed = True
                recvQueue.put(None)
                try:
                    if streamSource == OurStream:
                        sendWaitSocket._send(0, "", -streamId) #send stream terminator
                    else:
                        sendWaitSocket._send(0, "", streamId) #send stream terminator 
                except:
                    pass
        def msg(self):
            return startMsg
    return HNetStream()

def mkPacket(msg, messageId, parentSocket, stream):
    class Packet:
        def respond(_, msg):
            parentSocket.send(msg, responseTo = messageId)
        def respondAndWait(_, msg):
            return parentSocket.sendAndWait(msg, responseTo = messageId)
        def msg(_):
            return msg
        def _messageId(_):
            return messageId
        def proxy(_):
            if stream:
                return HNetProxy(HNetPickleStream(HNetSendWait(stream)))
            else:
                raise Exception("Tried to create proxy on a non-stream object.\nYou were probably expecting a stream but the other side sent a regular message.")
        def bigMsg(_):
            if stream:
                data = ""
                for chunk in stream.recv():
                    data += chunk
                return data
            else:
                raise Exception("Tried to create recv bigMsg on a non-stream object.\nYou were probably expecting a stream but the other side sent a regular message.")
    return Packet()
    
class HNetProxy:
    def __init__(self, stream):
        self.stream = stream
        def dummyRead():
            for _ in stream.recv():
                pass
        startNewThread(dummyRead)
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
    
    def sendAndWait(self, msg, responseTo = 0, timeout = None):
        messageId = self.__nextMessageId()
        self.waiters[messageId] = Queue()
        self._send(messageId, msg, responseTo)
        resp = self.waiters[messageId].get(True, timeout)
        if resp == None:
            raise StreamClosedBeforeReply
        del self.waiters[messageId]
        return resp
    
    def sendAndStream(self, msg, responseTo = 0):
        streamId = self.__nextStreamId()
        queue = Queue()
        self.waiters[streamId] = queue
        self._send(streamId, msg, responseTo)
        return newStream(None, self, streamId, queue, OurStream)
        
    def sendBigMsg(self, msg, bigMsg, responseTo = 0):
        stream = self.sendAndStream(msg, responseTo)
        while len(bigMsg) > 12000:
            stream.send(bigMsg[:1200])
            bigMsg = bigMsg[1200:]
        stream.send(bigMsg)
        stream.close()
    
    def sendProxy(self, obj, msg = "", responseTo = 0):
        stream = HNetPickleStream(HNetSendWait(self.sendAndStream(msg, responseTo)))
        def handleProxyStream():
            for packet in stream.recv():
                name, args, kwargs = packet.msg()
                try:
                    if name in [x for x in obj.__class__.__dict__.keys() if x[0] != "_"]:
                        packet.respond( (None, getattr(obj, name)(*args, **kwargs)) )
                except Exception,x:
                    packet.respond( ((sys.exc_info()[0], sys.exc_info()[1].args,  ''.join(traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback))), None) )
        startNewThread(handleProxyStream)
      
    def recv(self):
        for data in self.stream.recv():
            messageId, responseTo = struct.unpack('!ll', data[:8])
            msg = data[8:]
            if messageId > 0 and responseTo == 0:  # normal packet
                yield mkPacket(msg, messageId, self, None)
                
            elif messageId < 0 and responseTo == -1:  #packet on one of their streams,
                if messageId in self.theirStreams:
                    self.theirStreams[messageId].put(msg)
                    
            elif messageId < 0 and responseTo == -2:  #packet on one of our streams,
                if messageId in self.waiters:
                    self.waiters[messageId].put(msg)
                    
            elif messageId > 0 and responseTo > 0:  # response packet
                if responseTo in self.waiters:
                    self.waiters[responseTo].put(mkPacket(msg, messageId, self, None))
                    
            elif messageId < 0 and responseTo >= 0:  # start of stream packet (might also be a response)
                queue = Queue()
                self.theirStreams[messageId] = queue
                packet = mkPacket(msg, messageId, self, newStream(msg, self, messageId, queue, TheirStream))
                if responseTo == 0:
                    yield packet
                else:
                    self.waiters[messageId].put(packet)
                
            elif messageId == 0 and responseTo > 0:  # close their stream
                responseTo = -responseTo
                if responseTo in self.theirStreams:
                    self.theirStreams[responseTo].put(None)
                    del self.theirStreams[responseTo]
                    
            elif messageId == 0 and responseTo < 0:  # close our stream
                if responseTo in self.waiters:
                    self.waiters[responseTo].put(None)
                    del self.waiters[responseTo]
                    
        self.close()
        
    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                for q in self.waiters.values():
                    q.put(None)
                self.waiters = {}
                for q in self.theirStreams.values():
                    q.put(None)
                self.theirStreams = {}
                self.stream.close()
            
            
            
            
