# Echo client program
from socket import *

HOST = 'madarrow.changeip.org'    # The remote host
PORT = 6112               # The same port as used by the server
s = socket(AF_INET, SOCK_DGRAM)
s.connect((HOST, PORT))
while 1:
    data = raw_input('>> ')
    if not data:
        s.send(data)
        break
    else:
        s.send(data)
data, addr = s.recvfrom(4096)
print len(data)
s.close()
print 'Received', repr(data), addr