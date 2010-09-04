# Echo client program
import socket
import pickle
import sys
import struct
import hnet


class TCPClient():
    def __init__(self, host, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))

    def send(self, data):
        hnet.send(self.socket, data)

    #def recv(self):
    #    (length,) = struct.unpack('!L', self._recv(4))
    #    return pickle.loads(_recv(length))
        
    def recvServer(self):
        t = hnet.recv(self.socket)
        data = hnet.recv(self.socket)
        return (t, pickle.loads(data))

HOST = 'madarrow.changeip.org'    # The remote host
PORT = 6112                       # The same port as used by the server

client = TCPClient(HOST, PORT)

client.send("bla")
client.send(134253)

print client.recvServer()
print client.recvServer()
client.socket.close()
# print client.recvServer()
