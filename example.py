from hnet import *


"""
This library can actually do alot more than what is currently shown in the examples. 
I'll add more to this eventually.
There is a low level TCP socket that can do almost anything a regular TCP socket can, but is
  more pythonic and more consistent between platforms.
You can make several other kinds of streams: byte streams, packet streams, replyable streams, and pickled replyable streams

"""

examplePort = 30131

bigMsg = 'bla bla bla' * 5000

class FriendsList:
    def __init__(self):
        self.friends = []
    def addFriend(self, name):
        self.friends.append(name)
    def getFriends(self):
        return self.friends

def server(serverSocket, addr):
    def getBigMsg(packet):
        data = packet.bigMsg()
        print "We've recieved a big message! It was %i bytes long!" % len(data)
    friends = FriendsList()
    friends.addFriend('Mary')
    friends.addFriend('Bob')
    with serverSocket:
        for packet in serverSocket.recvs():
            if packet.msg() == 'Hello good fellow!':
                packet.reply('Good day sir!')
            elif isinstance(packet.msg(), list):
                print "We've recived the list: ", packet.msg()
            elif packet.msg() == 'big msg':
                startNewThread(getBigMsg, (packet,))
            elif packet.msg() == 'May I see your friends list?':
                packet.replyWithProxy(friends)
    print 'Now our friends are: ', friends.getFriends()

def client():
    with connectTCP('localhost', examplePort) as clientSocket:
        reply = clientSocket.sendAndWait('Hello good fellow!')
        if reply == 'Good day sir!':
            print 'He called me sir!'
        # the sending of a bigMsg happens in another thread
        #   also bigMsg must be a string of bytes
        clientSocket.sendBigMsg(bigMsg, 'big msg')
        clientSocket.send([4, 3, 5, 1]) # can send any pickleable object
        reply = clientSocket.sendAndWait('May I see your friends list?')
        # proxies only forwards methods calls, so you must use getters and setters
        #   most exceptions on the remote end with be trapped and returned to you
        friends = reply.proxy()
        print 'Our friends are: ', friends.getFriends()
        friends.addFriend('alice')
        del friends # remove reference to proxy so that it will release the stream 
                    # (usually you don't have to worry about it, I put it here mostly for demonstration)
        clientSocket.waitForStreams() # waits for any proxies or streams or bigMsgs to finish
        
        
      

def runExampleClientServer():
    with HNetTCPServer([('', examplePort)], server):
        clientThread = startNewThread(client)
        clientThread.join(1.0)
    return True

if __name__ == '__main__':
    runExampleClientServer()
