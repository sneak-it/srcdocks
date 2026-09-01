#!/usr/bin/env python3
"""Fakes an A2S server per the Valve wiki reply variants and checks healthcheck.sh agrees.

https://developer.valvesoftware.com/wiki/Server_queries
"""

import socket
import subprocess
import threading
from pathlib import Path

SCRIPT = Path(__file__).with_name('healthcheck.sh')

# Byte sequences below are the examples from the wiki, verbatim

REQUEST = bytes.fromhex("""
	FF FF FF FF 54 53 6F 75 72 63 65 20 45 6E 67 69
	6E 65 20 51 75 65 72 79 00
""")

CHALLENGE = bytes.fromhex('FF FF FF FF 41 0A 08 5E EA')

CHALLENGED_REQUEST = bytes.fromhex("""
	FF FF FF FF 54 53 6F 75 72 63 65 20 45 6E 67 69
	6E 65 20 51 75 65 72 79 00 0A 08 5E EA
""")

# Counter-Strike: Source reply
SOURCE = bytes.fromhex("""
	FF FF FF FF 49 02 67 61 6D 65 32 78 73 2E 63 6F
	6D 20 43 6F 75 6E 74 65 72 2D 53 74 72 69 6B 65
	20 53 6F 75 72 63 65 20 23 31 00 64 65 5F 64 75
	73 74 00 63 73 74 72 69 6B 65 00 43 6F 75 6E 74
	65 72 2D 53 74 72 69 6B 65 3A 20 53 6F 75 72 63
	65 00 F0 00 05 10 04 64 6C 00 00 31 2E 30 2E 30
	2E 32 32 00
""")

# Header 'm' reply that the wiki notes some older titles send alongside the Source one
GOLDSRC = bytes.fromhex('FF FF FF FF 6D') + b'192.168.1.5:27015\x00old server\x00dod_avalanche\x00dod\x00'

received = []


def serve(sock, replies, challenged):
    while True:
        data, addr = sock.recvfrom(2048)
        received.append(data)
        if challenged and not data.endswith(CHALLENGE[5:]):
            sock.sendto(CHALLENGE, addr)
            continue
        for reply in replies:
            sock.sendto(reply, addr)


def check(port, replies=(), challenged=False):
    if replies:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', port))
        threading.Thread(target=serve, args=(sock, replies, challenged), daemon=True).start()
    env = {'HEALTH_IP': '0.0.0.0', 'HEALTH_PORT': str(port), 'PATH': '/usr/bin:/bin'}
    return subprocess.run(['bash', SCRIPT], env=env, capture_output=True)


cases = [
    ('direct reply', [SOURCE], False, 27411),
    ('challenged reply', [SOURCE], True, 27412),
    ('goldsrc packet first', [GOLDSRC, SOURCE], False, 27413),
    ('goldsrc packet second', [SOURCE, GOLDSRC], False, 27414),
]

for label, replies, challenged, port in cases:
    received.clear()
    res = check(port, replies, challenged)
    print(f'{label}: exit={res.returncode} out={res.stdout!r}')
    assert res.returncode == 0, label
    assert b'game2xs.com Counter-Strike Source #1' in res.stdout, label
    assert received[0] == REQUEST, f'{label}: bad request {received[0]!r}'
    if challenged:
        assert received[1] == CHALLENGED_REQUEST, f'{label}: bad retry {received[1]!r}'

# IP=0.0.0.0 is a bind address, not a destination, so the check has to fall back to the hostname
host_addr = socket.gethostbyname(socket.gethostname())
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((host_addr, 27417))
threading.Thread(target=serve, args=(sock, [SOURCE], False), daemon=True).start()
res = subprocess.run(['bash', SCRIPT], env={'IP': '0.0.0.0', 'PORT': '27417', 'PATH': '/usr/bin:/bin'},
                     capture_output=True)
print(f'wildcard IP: exit={res.returncode} out={res.stdout!r}')
assert res.returncode == 0, 'wildcard IP'

res = check(27415)  # nothing listening
print(f'no server: exit={res.returncode}')
assert res.returncode == 1, 'no server'

res = check(27416, [GOLDSRC])  # only a GoldSource reply, no Source header to find
print(f'goldsrc only: exit={res.returncode}')
assert res.returncode == 1, 'goldsrc only'

print('all ok')
