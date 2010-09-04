import socket
import pickle
import time

import struct
import thread
import hnet

class TCPServer():
    def __init__(self, host, port):
        #Start listening on TCP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((host, port))
        self.socket.listen(1)

        self.clients = []
        self.done = False
        thread.start_new_thread(self.acceptConnections, ())

    def stop(self):
        self.done = True

    def acceptConnections(self):
        while not self.done:
            conn, addr = self.socket.accept()
            self.clients.append((conn, addr))
            thread.start_new_thread(self.readData, (conn, addr))

    def readData(self, conn, addr):
        try:
            while not self.done:
                data = hnet.recvData(conn)
                t = time.time()
                if not data: break
                print "recieved data:", addr
                for c, a in self.clients:
                    #print a
                    print "  sending to :", a
                    self._send(c, a, t, data)
        except socket.error, msg:
            print "Socket error: ", addr, msg
        finally:
            conn.close()
            self.clients.remove((conn,addr))
    def _send(self, conn, addr, t, data):
        try:
            hnet.send(conn, t)
            hnet.send(conn, data)
        except socket.error, msg:
           print "Socket error: ", addr, msg
           # make this work ok, even if connection is not in the list
           self.clients.remove((conn,addr))
           conn.close()
    


HOST = ''    # Symbolic name meaning all available interfaces
PORT = 6112  # Arbitrary non-privileged port

server = TCPServer(HOST,PORT)
raw_input(">> ")
#server.stop()