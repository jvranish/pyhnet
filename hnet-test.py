import unittest
import threading
from hnet import *


testPort = 30131

class TestHNet(unittest.TestCase):
        
    #def test_TCPConnectAndClose(self):
    #    def handleConnect(s, addr):
    #      s.close()
    #      stop()
    #    listenThread, stop = listenTCP([('', 30123)], handleConnect)
    #    self.assertTrue(listenThread.isAlive())
    #    connectTCP('localhost', 30123)
    #    listenThread.join()
    #    self.assertTrue(not listenThread.isAlive())

    def test_HNetSocketTCPServerSendClientRecv(self):
        def forServer(s):
            s.send("asdf")
            s.send("1234")
            s.send("the quick brown fox jump over whatever")
            s.close()
            
        def forClient(s):
            self.assertEqual([x for x in s.recv()], ["asdf", "1234", "the quick brown fox jump over whatever"])
        connectAndRun(forServer, forClient)
        
    def test_thing2(self):
        self.assertEqual(1, 1)
        
    def test_thing3(self):
        a = 5
        self.assertRaises(AttributeError, lambda x: getattr(a, x), "asdf")

def connectAndRun(serverStuff, clientStuff):
    def handleConnect(serverSocket, addr):
        serverThread = Thread(target = serverStuff, args = (serverSocket,))
        serverThread.start()
        serverThread.join()
        

    listenThread, stopListening = listenTCP([('', testPort)], handleConnect)
    clientSocket = connectTCP('localhost', testPort)
    clientThread = Thread(target = clientStuff, args = (clientSocket,))
    clientThread.start()
    clientThread.join()

    stopListening()
    listenThread.join()


        

if __name__ == '__main__':
    
    unittest.main()
    
