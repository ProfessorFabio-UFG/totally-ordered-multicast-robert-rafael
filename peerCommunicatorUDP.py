
from socket import *
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

# Creating a script map for the messages
script_map = {
    0: [
        "Solicitação de status do sistema.",
        "Requisição de tempo de resposta média.",
        "Finalizando verificação."
    ],
    1: [
        "Processo 1: Recebido status, iniciando coleta de métricas.",
        "Processo 1: Tempo médio de resposta: 120ms.",
        "Processo 1: Encerrando tarefas de monitoramento."
    ],
    2: [
        "Processo 2: Confirmando recebimento de status.",
        "Processo 2: Alerta! Tempo acima do esperado.",
        "Processo 2: Log enviado ao servidor."
    ],
    3: [
        "Processo 3: Coleta paralela em andamento.",
        "Processo 3: Sincronização com o banco concluída.",
        "Processo 3: Fechando sessão de análise."
    ],
    4: [
        "Processo 4: Iniciando backup dos dados.",
        "Processo 4: Backup finalizado com sucesso.",
        "Processo 4: Estado persistido com sucesso."
    ],
    5: [
        "Processo 5: Verificando integridade do sistema.",
        "Processo 5: Nenhuma inconsistência detectada.",
        "Processo 5: Aguardando novas instruções."
    ]
}

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

def aguardar_entrega_pendente(logList, message_buffer, message_acks, recvSocket, timeout=5):
    print("Todos os peers enviaram -1. Aguardando últimos ACKs...")

    import time
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            recvSocket.settimeout(0.5)
            msgPack = recvSocket.recv(1024)
            msg = pickle.loads(msgPack)

            if isinstance(msg, dict) and msg.get("type") == "ack":
                ack_key = (msg['timestamp'], msg['sender_id'])
                if ack_key not in message_acks:
                    message_acks[ack_key] = set()
                if msg['ack_from'] not in message_acks[ack_key]:
                    message_acks[ack_key].add(msg['ack_from'])

        except timeout:
            pass

        message_buffer.sort()
        i = 0
        while i < len(message_buffer):
            timestamp, sender_id, content = message_buffer[i]
            key = (timestamp, sender_id)
            if len(message_acks.get(key, set())) == N:
                logList.append((timestamp, sender_id, content))
                print(f"✔️  Entregue após -1: ({sender_id}, {content})")
                message_buffer.pop(i)
            else:
                i += 1

        if len(message_buffer) == 0:
            break

        print("🕓 Aguardando entrega de mensagens restantes...")

    recvSocket.settimeout(None)

class MsgHandler(threading.Thread):
  def __init__(self, sock):
    threading.Thread.__init__(self)
    self.sock = sock

  def run(self):
    print('Handler is ready. Waiting for the handshakes...')

    global handShakeCount, lamport_clock, message_buffer, message_acks, myself, nMsgs

    logList = []

    while handShakeCount < N:
        time.sleep(0.1)
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
            if msg.get('type') == 'ack':
                ack_key = (msg['timestamp'], msg['sender_id'])
                if ack_key not in message_acks:
                    message_acks[ack_key] = set()

                if msg['ack_from'] not in message_acks[ack_key]:
                    message_acks[ack_key].add(msg['ack_from'])

            else:
                sender_id = msg['sender_id']
                timestamp = msg['timestamp']
                content = msg['content']
                lamport_clock = max(lamport_clock, timestamp) + 1
                print(f"[Lamport Clock={lamport_clock}] Received from {sender_id}: {content}")

                key = (timestamp, sender_id)
                if key not in message_acks:
                    message_acks[key] = set()
                    message_buffer.append((timestamp, sender_id, content))

                # Enviar ACK para todos os peers, incluindo a si mesmo
                ack_msg = {
                    'type': 'ack',
                    'timestamp': timestamp,
                    'sender_id': sender_id,
                    'ack_from': myself
                }
                ackPack = pickle.dumps(ack_msg)
                for addrToSend in PEERS:
                    sendSocket.sendto(ackPack, (addrToSend, PEER_UDP_PORT))

        elif msg[0] == -1:
            stopCount += 1
            if stopCount == N:
              aguardar_entrega_pendente(logList, message_buffer, message_acks, self.sock)
              break

        message_buffer.sort(key=lambda x: (x[0], x[1]))
        i = 0
        while i < len(message_buffer):
            (timestamp, sender_id, content) = message_buffer[i]
            key = (timestamp, sender_id)
            if len(message_acks.get(key, set())) == N:
                logList.append((timestamp, sender_id, content))
                print(f"Delivered message from {sender_id}: {content}")
                message_buffer.pop(i)
            else:
                i += 1

    message_buffer.sort(key=lambda x: (x[0], x[1]))
    for (timestamp, sender_id, content) in message_buffer:
        key = (timestamp, sender_id)
        if len(message_acks.get(key, set())) == N:
            logList.append((timestamp, sender_id, content))
            print(f"Delivered (final) from {sender_id}: {content}")

    expected = N * nMsgs
    if len(logList) < expected:
        print(f"⚠️  Atenção: log incompleto — esperado {expected}, recebido {len(logList)}")

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

  time.sleep(5)

  msgHandler = MsgHandler(recvSocket)
  msgHandler.start()
  print('Handler started')

  PEERS = getListOfPeers()

  for addrToSend in PEERS:
    print('Sending handshake to ', addrToSend)
    msg = ('READY', myself)
    msgPack = pickle.dumps(msg)
    sendSocket.sendto(msgPack, (addrToSend,PEER_UDP_PORT))

  print('Main Thread: Sent all handshakes. handShakeCount=', str(handShakeCount))

  while (handShakeCount < N):
    pass

  for msgNumber in range(0, nMsgs):
    time.sleep(random.randrange(10,100)/1000)
    lamport_clock += 1
    content = script_map.get(myself, [])[msgNumber] if msgNumber < len(script_map.get(myself, [])) else f"Mensagem técnica {msgNumber} do Processo {myself}"

    msg = {
      'sender_id': myself,
      'timestamp': lamport_clock,
      'content': content
    }
    msgPack = pickle.dumps(msg)
    for addrToSend in PEERS:
      sendSocket.sendto(msgPack, (addrToSend,PEER_UDP_PORT))
      print(f'[Lamport Clock={lamport_clock}] Sent message {msgNumber}')

  for addrToSend in PEERS:
    msg = (-1,-1)
    msgPack = pickle.dumps(msg)
    sendSocket.sendto(msgPack, (addrToSend, PEER_UDP_PORT))
