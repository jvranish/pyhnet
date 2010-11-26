from hnet import *

# Two short examples

examplePort = 30131

bigMsg = 'bla bla bla' * 5000

class FriendsList:
    def __init__(self, handlers):
        self.friends = []
        self.handlers = handlers
    def addFriend(self, name):
        self.friends.append(name)
        for handler in self.handlers:
            handler.send('Friend %s, has been added.' % name)
    def getFriends(self):
        return self.friends
        
class MyServer(HNetTCPServer):
    def onInit(self):
        self.clientHandlers = []
        self.friends = FriendsList(self.clientHandlers)   
        self.friends.addFriend('Mary')
        self.friends.addFriend('Bob')

class MyServerHandler(HNetHandler):
    def onRecv(self, packet):
        if packet.msg() == 'Hello good fellow!':
            packet.reply('Good day sir!')
        elif isinstance(packet.msg(), list):
            safePrint("We've recived the list: " + str(packet.msg()))
        elif packet.msg() == 'big msg':
            startNewThread(self.getBigMsg, (packet,))
        elif packet.msg() == 'May I see your friends list?':
            packet.replyWithProxy(self.server.friends)
    
    def getBigMsg(self, packet):
        data = packet.bigMsg()
        safePrint("We've recieved a big message! It was %i bytes long!" % len(data))  
    
    def onInit(self):
        self.server.clientHandlers.append(self)
        
    def onClose(self):
        safePrint('Now our friends are: ' + str(self.server.friends.getFriends()))
        self.server.clientHandlers.remove(self)

        
class MyClientHandler(HNetHandler):
    def runConnection(self):
        reply = self.sendAndWait('Hello good fellow!')
        if reply.msg() == 'Good day sir!':
            safePrint('He called me sir!')
        # the sending of a bigMsg in another thread
        #   also bigMsg must be a string of bytes
        bigMsgFinished = self.sendBigMsg(bigMsg*8, 'big msg')
        self.send([4, 3, 5, 1]) # can send any pickleable object
        self.sendBigMsg(bigMsg, 'big msg').wait()
        reply = self.sendAndWait('May I see your friends list?')
        # proxies only forwards methods calls, so you must use getters and setters
        #   most exceptions on the remote end with be trapped and thrown locally
        friends = reply.proxy()
        safePrint('Our friends are: ' + str(friends.getFriends()))
        friends.addFriend('alice')
        bigMsgFinished.wait() # make sure we've finished sending this before we disconnect

        # NOTE! we disconnect when this function returns
        #  if you want to for the remote side to disconnect, you can do:
        #  self.done.wait()
        
    def onRecv(self, packet):
        safePrint(packet.msg())

def runExampleClientServer():
    with MyServer([('', examplePort)], MyServerHandler):
        MyClientHandler(connectTCP('localhost', examplePort)).run().wait(1.0)

# A simple fetch of a webpage. Doing this with just the socket library would be
#  a pain
def runExampleSimpleTCP():
    with connectTCP('google.com', 80, socketConstructor = TCPSocket) as s:
        s.send("GET / HTTP/1.0\r\n\r\n")
        response = ''.join(s.recvs())
        safePrint(response[:15])

#
#
#  The stuff below here is mostly just for testing
#    (for the perposes of the example, ignore it)
#

#List of expected outputs (So I can use my example as a test case :) )
results = [ "He called me sir!"
          , "We've recived the list: [4, 3, 5, 1]"
          , "We've recieved a big message! It was 55000 bytes long!"
          , "Our friends are: ['Mary', 'Bob']"
          , "Friend alice, has been added."
          , "We've recieved a big message! It was 440000 bytes long!"
          , "Now our friends are: ['Mary', 'Bob', 'alice']"
          , 'HTTP/1.0 200 OK'
          ]

# thread safe print that keeps the lines from interleaving 
#  it also checks against expected output
printLock = Lock()
enablePrint = False
def safePrint(s):
    with printLock:
        if s in results:
            results.remove(s)
            if enablePrint:
                print s
        else:
            raise Exception, "Error in example, %s" % s
        
def runExamples():
    runExampleClientServer()
    runExampleSimpleTCP()
    if results: raise Exception, "Error in example"
        
if __name__ == '__main__':
    enablePrint = True
    runExamples()
    
