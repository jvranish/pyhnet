import unittest
import threading
import socket
import select
import time
from hnet import *


testPort = 30131

# sanity checker
class TestSocket(unittest.TestCase):
    def asdftest_SocketTCPAcceptClose(self):
        serverListenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serverListenSocket.bind(('localhost', testPort))
        serverListenSocket.listen(5)
        serverListenSocket.settimeout(0.01)
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
        
        thread.join(1.0)
        self.assertFalse(thread.isAlive())
        
    def test_SocketTCPReadUnblockOnShutdown(self):
        serverListenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serverListenSocket.bind(('localhost', testPort))
        serverListenSocket.listen(5)
        serverListenSocket.settimeout(0.01)
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
        def closer():
            time.sleep(0.01)
            #clientSocket.shutdown(socket.SHUT_RDWR)
            #clientSocket._sock.close()
            clientSocket.close()
            
        startNewThread(closer)
        r, w, e = select.select([clientSocket],[],[], None)
        try:
          clientSocket.recv(20)
        except:
          pass
        done.set()
        thread.join(1.0)
        serverListenSocket.close()
        self.assertFalse(thread.isAlive())

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
        
    def test_TCPConnectAndClose(self):
        def handleConnect(s, addr):
          listenThread.stopListening()
        listenThread = listenTCP([('', testPort)], handleConnect)
        self.assertTrue(listenThread.isAlive())
        with connectTCP('localhost', testPort) as _:
            pass
        listenThread.join(1.0)
        self.assertFalse(listenThread.isAlive())

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
        
    def test_HNetProxy(self):
        
        
        def forServer(s):
            s = HNetSendWait(s)
            
            def runTest(s, obj):
                self.assertEqual(obj.getA(), 5)
                obj.setA(10)
                self.assertEqual(obj.getA(), 10)
                self.assertRaises(TypeError, obj.testError)
                
                time.sleep(0.01)
                #print "done waiting"
                s.close()
                
                
            for packet in s.recv():
                if packet.msg() == 'testProxy':
                    obj = getProxy(packet)
                    startNewThread(runTest, (s, obj))
               
            
        def forClient(s):
            s = HNetSendWait(s)
            testObj = TestObj(5)
            s.sendProxy(testObj, 'testProxy')
            for packet in s.recv():
                pass
            s.close()
            self.assertEqual(testObj.a, 10)
            
            
        self.connectAndRun(forServer, forClient)
      
        
    def connectAndRun(self, serverStuff, clientStuff):
        x = {}
        #TODO fix this, figure out a better way to track the serverStuff thread
        #  maybe start thread automatically? no? hmmm
        def handleConnect(serverSocket, addr):
            def runServerStuff():
                with serverSocket as s:
                    serverStuff(s)
            x['serverThread'] = startNewThread(runServerStuff)
            

        listenThread = listenTCP([('', testPort)], handleConnect, 0.01)
        def clientThread():        
            with connectTCP('localhost', testPort) as clientSocket:
                clientStuff(clientSocket)
        ct = startNewThread(clientThread)
        ct.join(1.0)
        listenThread.stopListening()
        listenThread.join(1.0)
        x['serverThread'].join(1.0)
        self.assertFalse(x['serverThread'].isAlive())
        self.assertFalse(ct.isAlive())
        self.assertFalse(listenThread.isAlive())


        

if __name__ == '__main__':
    unittest.main()
    
