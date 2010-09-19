import unittest
import threading
from threading import Event, Lock, Condition
import socket
import select
import time
from hnet import *


testPort = 30131

# sanity checker
class TestSocket(unittest.TestCase):
    def threadStops(self, thread):
        thread.join(1.0)
        self.assertFalse(thread.isAlive())
        
    def test_SocketTCPAcceptClose(self):
        serverListenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serverListenSocket.bind(('localhost', testPort))
        serverListenSocket.listen(5)
        serverListenSocket.settimeout(0.001)
        done = Event()
        def acceptor():
            while not done.isSet():
                try:
                    conn, addr = serverListenSocket.accept()
                except socket.timeout:
                    pass
            
        thread = startNewThread(acceptor)
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect(('localhost', testPort))
        clientSocket.close()
        done.set()
        serverListenSocket.close()
        self.threadStops(thread)
        
    def test_SocketTCPReadUnblockOnShutdown(self):
        serverListenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serverListenSocket.bind(('localhost', testPort))
        serverListenSocket.listen(5)
        serverListenSocket.settimeout(0.001)
        done = Event()
        def acceptor():
            while not done.isSet():
                try:
                    conn, addr = serverListenSocket.accept()
                except socket.timeout:
                    pass
                except socket.error, e:
                    if not done.isSet():
                        raise
                
        thread = startNewThread(acceptor)
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect(('localhost', testPort))
        def closer():
            time.sleep(0.01)
            clientSocket.shutdown(socket.SHUT_RDWR)
            clientSocket.close()
            
            
        done.set()
        serverListenSocket.close()
        closerThread = startNewThread(closer)
        
        clientSocket.recv(1)
        
        self.threadStops(thread)
        self.threadStops(closerThread)

class TestObj():
    def __init__(self, a):
        self.a = a
    def setA(self, a):
        self.a = a
    def getA(self):
        return self.a
    def testError(self):
        return 1 + ''
                
class TestHNet(unittest.TestCase):
  
    def setUp(self):
        self.client = None
        self.server = None
        self.listen = None
        
    def tearDown(self):
        if self.client:
            self.client.close()
        if self.server:
            self.server.close()
        if self.listen:
            self.listen.stop()
        
    def test_TCPConnectAndClose(self):
        def handleConnect(s, addr):
            pass
        server = HNetTCPServer([('', testPort)], handleConnect)
        server.start()
        self.assertTrue(server.thread.isAlive())
        with connectTCP('localhost', testPort) as _:
            pass
        server.stop()
        self.threadStops(server.thread)
        
    def test_TCPBindPortInvalid(self):
        server = HNetTCPServer([('', testPort), ('', testPort)], lambda s, addr: None)
        self.assertRaises(ServerStartFail, server.start)
        
    def test_TCPBindHostInvalid(self):
        server = HNetTCPServer([('someInvalidHostName', testPort)], lambda s, addr: None)
        self.assertRaises(HostInvalid, server.start)
        
    def test_TCPConnectHostInvalid(self):
        def tryConnect():
            with connectTCP('someInvalidHostName', testPort, timeout = 0.000001) as _:
                pass
        self.assertRaises(HostInvalid, tryConnect)
        
    def test_TCPConnectRejected(self):
        def tryConnect():
            with connectTCP('localhost', testPort, timeout = 0.000001) as _:
                pass

        self.assertRaises(ConnectFailed, tryConnect)
    
    def test_TCPConnectReset(self):
        serverListenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serverListenSocket.bind(('localhost', testPort))
        serverListenSocket.listen(1)
        def tryConnect():
            with connectTCP('localhost', testPort, timeout = 0.00001) as s:
                serverListenSocket.close()
                s.send('asdf')
            
        self.assertRaises(ConnectionClosed, tryConnect)
    
    
    def test_HNetSocketTCPServerSendClientRecv(self):
        def forServer(s):
            s.send("asdf")
            s.send("1234")
            s.send("the quick brown fox jumps over whatever")
            s.close()
            
        def forClient(s):
            self.assertEqual([x for x in s.recv()], ["asdf", "1234", "the quick brown fox jumps over whatever"])
            s.close()
        self.connectAndRun(forServer, forClient)
        
    def test_HNetSocketTCPBrokenPipe(self):
        def forServer(s):
            def doSend():
                while True:
                  s.send("the quick brown fox jumps over whatever")
            self.assertRaises(ConnectionClosed, doSend)
            s.close()
            
        def forClient(s):
            for packet in s.recv():
                s.close()

        self.connectAndRun(forServer, forClient)
        
    #TODO add case for shutdown while waiting for a response
        
    def test_HNetProxy(self):
        
        def forServer(s):
            s = HNetSendWait(s)
            
            def runTest(s, obj):
                self.assertEqual(obj.getA(), 5)
                obj.setA(10)
                self.assertEqual(obj.getA(), 10)
                self.assertRaises(TypeError, obj.testError)
                s.close()
            
            for packet in s.recv():
                if packet.msg() == 'testProxy':
                    startNewThread(runTest, (s, packet.proxy()))
               
        def forClient(s):
            s = HNetSendWait(s)
            testObj = TestObj(5)
            s.sendProxy(testObj, 'testProxy')
            for _ in s.recv():
                pass
            
            s.close()
            self.assertEqual(testObj.a, 10)
            
        self.connectAndRun(forServer, forClient)
        
    def test_HNetBigMsg(self):
        bigMsg = 'This is a big message maybe'*5000
        def forServer(s):
            s = HNetSendWait(s)
            
            def runTest(s, packet):
                recievedBigMsg = packet.bigMsg()
                self.assertEqual(bigMsg, recievedBigMsg)
                s.close()
            
            for packet in s.recv():
                if packet.msg() == 'my big message':
                    startNewThread(runTest, (s, packet))
               
        def forClient(s):
            s = HNetSendWait(s)
            startNewThread(s.sendBigMsg, ('my big message', bigMsg))
            for _ in s.recv():
                pass
            
            s.close()
            
        self.connectAndRun(forServer, forClient)
      
    def connectAndRun(self, serverStuff, clientStuff):
        serverDone  = Event()
        def handleConnect(serverSocket, addr):
            with serverSocket as s:
                self.server = serverSocket
                serverStuff(s)
            serverDone.set()

        server = HNetTCPServer([('', testPort)], handleConnect, 0.001)
        self.listen = server
        server.start()
        def runClientStuff():        
            with connectTCP('localhost', testPort) as clientSocket:
                self.client = clientSocket
                clientStuff(clientSocket)
        clientThread = startNewThread(runClientStuff)
        self.threadStops(clientThread)
        server.stop()
        self.threadStops(server.thread)
        serverDone.wait(1.0)
        self.assertTrue(serverDone.isSet())
    
    def threadStops(self, thread):
        thread.join(1.0)
        self.assertFalse(thread.isAlive())
        

if __name__ == '__main__':
    unittest.main()
    
