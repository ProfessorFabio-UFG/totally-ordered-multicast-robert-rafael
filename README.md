[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/TyBiAFsA)
# MPComm
Very simple demo of multicast communication without coordination.
A set of peer processes is established and each process multicasts a sequence of messages to all other processes at random intervals. Messages are stamped with the ID of the sending process and a local sequence number defined by the sending process. This is a simple attempt to demonstrate the problem of message ordering (or, in this version, the lack of it).

The peer processes run the PeerCommunicatorUDP.py program, which has two separate threads, one for sending and the other for receiving messages. A basic handshaking protocol is used to synchronize the processes before they actually start multicasting the sequence of messages. Also, a fixed timer is set to allow plenty of time to start all processes on the participating machines. At the end, each process sends the sequence received messages to a server, which compares the sequences of messages received by all the processes to determine the number of messages received out of order (actually, the number of rounds in which at least one process received a different message form the others).


In order to actually see the problem, it is necessary to run the peer processes on different networks (e.g., run some of the processes in one region of the cloud, whereas the others are run on another region).


### Lampart Clock

O algoritmo implementado utiliza relógios lógicos de Lamport para garantir a ordenação total das mensagens trocadas entre processos em um sistema distribuído. Cada processo mantém um contador lógico, que é incrementado a cada envio de mensagem. Ao receber uma mensagem, o processo ajusta seu relógio lógico com base no valor recebido, garantindo que todos os eventos sigam uma ordem causal.
As mensagens são enviadas contendo o valor do relógio no momento do envio, permitindo que os receptores ordenem corretamente os eventos recebidos. Com isso, todos os processos mantêm um histórico de mensagens em uma ordem consistente, mesmo em ambientes com diferentes atrasos de rede.

