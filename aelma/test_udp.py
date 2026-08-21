#!/usr/bin/env python
import socket
import time

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
samples = ["DEPTH=45.2", "DEPTH=52.8", "DEPTH=38.1", "48.5m", "42.3"]

for sample in samples:
    sock.sendto(sample.encode(), ("localhost", 50000))
    print(f"Sent UDP depth: {sample}")
    time.sleep(0.1)

print("UDP depth test complete")
sock.close()
