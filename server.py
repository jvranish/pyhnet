# Echo server program
from socket import *
from thread import *


HOST = ''                 # Symbolic name meaning all available interfaces
PORT = 6112               # Arbitrary non-privileged port
s = socket(AF_INET, SOCK_DGRAM)
s.bind((HOST, PORT))

addr = ('madarrow.changeip.org', 6112)
done = False

def recieveThread():
    global addr
    global done
    while not done:
        data, addr = s.recvfrom(4096)
        print
        print data
        if not data:
          break
        #s.sendto(data, addr)
    s.close()
    done = True

def sendThread():
    global addr
    global done
    while not done:
        send = raw_input(">> ")
        if not send:
            break
        s.sendto(send, addr)
    done = True

start_new_thread(recieveThread, ())
start_new_thread(sendThread, ())

while not done:
  pass
