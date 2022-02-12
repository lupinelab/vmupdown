import socket

HOST = ""
PORT = 9

def wol_listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, PORT))
    while True:
        magic_packet = s.recv(128).hex()
        raw_mac = magic_packet.strip("f")[0:12]
        mac = ':'.join(raw_mac[i:i+2] for i in range(0, len(raw_mac), 2))
        print(mac)

