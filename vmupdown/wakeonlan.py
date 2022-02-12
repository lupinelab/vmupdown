import socket

HOST = ""
PORT = 9

def listen():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        packet = s.recv(128)
        if packet is not None:
            packet = packet.hex()