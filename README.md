
pyhnet: a high level python networking library
==============================================

Goal: to make networking in python much easier than it currently is.

### Key features:
* An easier to use TCP socket that can do almost anything the standard socket could
* Consistent error messages between platforms
* Unblock blocking operations on .close()
* Easy multiplexing of streams
* Easy reply/wait for reply
* Optional automatic pickling of messages
* Remote proxy objects. 
  you can send a proxy of a python object to the other side
  any methods called on the remote proxy will be sent through
  the connection and called on the local object. Any exceptions
  thrown in the call will be packaged up and sent back.

### Getting Started

There are a couple examples in example.py that should get you going.

### Description

pyhnet starts with the plain python sockets (which have a quite varying 
behavior between platforms) and adds a simple wrapper around it that gives
98% of the functionality of the plain sockets, but is much easier to use
and behaves consistently across platforms. 
Specifically, exceptions raised should always be the same for a given type 
of error and .close() will always unblock any blocking socket operations.

pyhnet provides several other wrappers than can be stacked together around 
the lower level byte stream to convert it to a packet stream, replyable 
packet stream or a pickled replyable packet stream. (the last, called
HNetTCPSocket, is the default)

I'm planning on adding support for UDP eventually but haven't gotten around to it yet.
If you have a burning need for it let me know; it shouldn't be very hard to add it.

Sorry the documentation is sparse, but the source is relatively readable (and short)

