from socket  import *
from constMP import * #-
import threading
import random
import time
import pickle
from requests import get

#handShakes = [] # not used; only if we need to check whose handshake is missing

# Counter to make sure we have received handshakes from all other processes
handShakeCount = 0

PEERS = []

# Lamport Logical Clock
handShakeCount = 0
message_acks = {}
message_buffer = []
lamport_clock = 0
nMsgs = 0

# UDP sockets to send and receive data messages:
# Create send socket
sendSocket = socket(AF_INET, SOCK_DGRAM)
#Create and bind receive socket
recvSocket = socket(AF_INET, SOCK_DGRAM)
recvSocket.bind(('0.0.0.0', PEER_UDP_PORT))

# TCP socket to receive start signal from the comparison server:
serverSock = socket(AF_INET, SOCK_STREAM)
serverSock.bind(('0.0.0.0', PEER_TCP_PORT))
serverSock.listen(1)


def get_public_ip():
  ipAddr = get('https://api.ipify.org').content.decode('utf8')
  print('My public IP address is: {}'.format(ipAddr))
  return ipAddr

# Function to register this peer with the group manager
def registerWithGroupManager():
  clientSock = socket(AF_INET, SOCK_STREAM)
  print ('Connecting to group manager: ', (GROUPMNGR_ADDR,GROUPMNGR_TCP_PORT))
  clientSock.connect((GROUPMNGR_ADDR,GROUPMNGR_TCP_PORT))
  ipAddr = get_public_ip()
  req = {"op":"register", "ipaddr":ipAddr, "port":PEER_UDP_PORT}
  msg = pickle.dumps(req)
  print ('Registering with group manager: ', req)
  clientSock.send(msg)
  clientSock.close()

def getListOfPeers():
  clientSock = socket(AF_INET, SOCK_STREAM)
  print ('Connecting to group manager: ', (GROUPMNGR_ADDR,GROUPMNGR_TCP_PORT))
  clientSock.connect((GROUPMNGR_ADDR,GROUPMNGR_TCP_PORT))
  req = {"op":"list"}
  msg = pickle.dumps(req)
  print ('Getting list of peers from group manager: ', req)
  clientSock.send(msg)
  msg = clientSock.recv(2048)
  PEERS = pickle.loads(msg)
  print ('Got list of peers: ', PEERS)
  clientSock.close()
  return PEERS

class MsgHandler(threading.Thread):
  def __init__(self, sock):
    threading.Thread.__init__(self)
    self.sock = sock

  def run(self):
    print('Handler is ready. Waiting for the handshakes...')

    global handShakeCount, lamport_clock, message_buffer, message_acks, myself, nMsgs

    logList = []

    while handShakeCount < N:
      msgPack = self.sock.recv(1024)
      msg = pickle.loads(msgPack)
      if msg[0] == 'READY':
        handShakeCount += 1
        print('--- Handshake received: ', msg[1])

    print('Secondary Thread: Received all handshakes. Entering the loop to receive messages.')

    stopCount = 0
    while True:
      msgPack = self.sock.recv(1024)
      msg = pickle.loads(msgPack)

      if isinstance(msg, dict):
        sender_id = msg['sender_id']
        timestamp = msg['timestamp']
        content = msg['content']

        lamport_clock = max(lamport_clock, timestamp) + 1
        print(f"[Lamport Clock={lamport_clock}] Received from {sender_id}: {content}")

        key = (timestamp, sender_id)

        if key not in message_acks:
          message_acks[key] = set()
          message_buffer.append((timestamp, sender_id, content))

        message_acks[key].add(sender_id)

        message_buffer.sort()

        print(f"DEBUG: message_acks[{key}] = {message_acks[key]}")
        print(f"DEBUG: buffer contains {len(message_buffer)} messages")

        while message_buffer:
          first = message_buffer[0]
          delivery_key = (first[0], first[1])
          if myself in message_acks.get(delivery_key, set()):
            logList.append(first)
            print(f"Delivered message from {first[1]}: {first[2]}")
            message_buffer.pop(0)
          else:
            break

      elif msg[0] == -1:
        stopCount += 1
        if stopCount == N:
          break


    expected_msg_count = N * nMsgs  # N peers × n mensagens cada

    if len(logList) < expected_msg_count:
      print(f"⚠️  Atenção: log incompleto — esperado {expected_msg_count}, recebido {len(logList)}")

    # Ainda assim salva o que tiver (útil para depuração)
    with open('logfile' + str(myself) + '.log', 'w') as logFile:
      logFile.writelines(str(logList))

    print('Sending the list of messages to the server for comparison...')
    clientSock = socket(AF_INET, SOCK_STREAM)
    clientSock.connect((SERVER_ADDR, SERVER_PORT))
    msgPack = pickle.dumps(logList)
    clientSock.send(msgPack)
    clientSock.close()

    handShakeCount = 0
    exit(0)

# Function to wait for start signal from comparison server:
def waitToStart():
  (conn, addr) = serverSock.accept()
  msgPack = conn.recv(1024)
  msg = pickle.loads(msgPack)
  myself = msg[0]
  nMsgs = msg[1]
  conn.send(pickle.dumps('Peer process '+str(myself)+' started.'))
  conn.close()
  return (myself,nMsgs)

# From here, code is executed when program starts:
registerWithGroupManager()
while 1:
  print('Waiting for signal to start...')
  (myself, nMsgs) = waitToStart()
  print('I am up, and my ID is: ', str(myself))

  if nMsgs == 0:
    print('Terminating.')
    exit(0)

  # Wait for other processes to be ready
  # To Do: fix bug that causes a failure when not all processes are started within this time
  # (fully started processes start sending data messages, which the others try to interpret as control messages) 
  time.sleep(5)

  # Create receiving message handler
  msgHandler = MsgHandler(recvSocket)
  msgHandler.start()
  print('Handler started')

  PEERS = getListOfPeers()
  
  # Send handshakes
  # To do: Must continue sending until it gets a reply from each process
  #        Send confirmation of reply
  for addrToSend in PEERS:
    print('Sending handshake to ', addrToSend)
    msg = ('READY', myself)
    msgPack = pickle.dumps(msg)
    sendSocket.sendto(msgPack, (addrToSend,PEER_UDP_PORT))
    #data = recvSocket.recvfrom(128) # Handshadke confirmations have not yet been implemented

  print('Main Thread: Sent all handshakes. handShakeCount=', str(handShakeCount))

  while (handShakeCount < N):
    pass  # find a better way to wait for the handshakes

  # Send a sequence of data messages to all other processes 
  for msgNumber in range(0, nMsgs):
    # Wait some random time between successive messages
    time.sleep(random.randrange(10,100)/1000)
    lamport_clock += 1
    msg = {
      'sender_id': myself,
      'timestamp': lamport_clock,
      'content': f'Message {msgNumber}'
    }
    msgPack = pickle.dumps(msg)
    msgPack = pickle.dumps(msg)
    for addrToSend in PEERS:
      sendSocket.sendto(msgPack, (addrToSend,PEER_UDP_PORT))
      print(f'[Lamport Clock={lamport_clock}] Sent message {msgNumber}')

  # Tell all processes that I have no more messages to send
  for addrToSend in PEERS:
    msg = (-1,-1)
    msgPack = pickle.dumps(msg)
    sendSocket.sendto(msgPack, (addrToSend,PEER_UDP_PORT))
