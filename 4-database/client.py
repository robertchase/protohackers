import socket
import sys


server = ("localhost", 12345)

client = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

while True:
    line = sys.stdin.readline().strip()
    client.sendto(line.encode(), server)
    if "=" not in line:
        message, address = client.recvfrom(1000)
        message = message.decode()
        print(message)
