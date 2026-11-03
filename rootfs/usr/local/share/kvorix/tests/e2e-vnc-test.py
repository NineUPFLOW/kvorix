#!/usr/bin/env python3
# E2E: noVNC-путь целиком — WS-handshake на /<token>/websockify через nginx,
# затем RFB 3.8 handshake + VNC-auth (DES) до SecurityResult. Печатает E2E-VNC-OK при успехе.
import socket, struct, base64, os, subprocess, sys

HOST, PORT = "127.0.0.1", 6080
token = subprocess.run(["sudo", "-n", "cat", "/etc/kvorix/novnc.token"],
                       capture_output=True, text=True).stdout.strip()
password = subprocess.run(["sudo", "-n", "cat", "/etc/kvorix/vnc.pass.txt"],
                          capture_output=True, text=True).stdout.strip()
assert len(token) == 48 and password, "нет токена/пароля"

s = socket.create_connection((HOST, PORT), timeout=8)
key = base64.b64encode(os.urandom(16)).decode()
req = ("GET /%s/websockify HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
       "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
       % (token, HOST, PORT, key))
s.sendall(req.encode())
resp = b""
while b"\r\n\r\n" not in resp:
    resp += s.recv(4096)
assert b"101" in resp.split(b"\r\n")[0], "WS handshake не 101: %r" % resp[:60]

buf = bytearray(resp.split(b"\r\n\r\n", 1)[1])  # остаток после заголовка — уже WS-фреймы

def recv_exact(n):
    global buf
    while len(buf) < n:
        chunk = s.recv(65536)
        if not chunk:
            raise RuntimeError("socket closed")
        buf += chunk
    out = bytes(buf[:n]); del buf[:n]
    return out

def ws_read():
    # прочитать один WS-фрейм (server->client, без маски), вернуть payload
    h = recv_exact(2)
    fin_op, ln = h[0], h[1] & 0x7F
    if ln == 126:
        ln = struct.unpack(">H", recv_exact(2))[0]
    elif ln == 127:
        ln = struct.unpack(">Q", recv_exact(8))[0]
    return recv_exact(ln)

def ws_send(data):
    # client->server, с маской
    mask = os.urandom(4)
    ln = len(data)
    if ln < 126:
        hdr = struct.pack(">BB", 0x82, 0x80 | ln)
    elif ln < 65536:
        hdr = struct.pack(">BBH", 0x82, 0x80 | 126, ln)
    else:
        hdr = struct.pack(">BBQ", 0x82, 0x80 | 127, ln)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    s.sendall(hdr + mask + masked)

stream = bytearray()

def vnc_read(n):
    global stream
    # читать ровно n байт протокола RFB поверх WS (фреймы могут дробить)
    while len(stream) < n:
        stream += ws_read()
    out = bytes(stream[:n]); del stream[:n]
    return out

print("step: читаю версию", flush=True)
ver = vnc_read(12)
print("step: версия", ver, flush=True)
assert ver.startswith(b"RFB "), ver
ws_send(b"RFB 003.008\n")
print("step: отправил версию", flush=True)
nsec = vnc_read(1)[0]
print("step: nsec", nsec, flush=True)
sectypes = vnc_read(nsec) if nsec else vnc_read(4)  # 3.8: count+types; 3.3: 4-байтный список
if nsec:
    assert 2 in sectypes, "нет VNC-auth: %r" % sectypes
    ws_send(bytes([2]))
else:
    t = struct.unpack(">I", sectypes)[0]
    assert t == 2, t
    ws_send(struct.pack(">I", 2))
print("step: sectypes", sectypes, flush=True)
challenge = vnc_read(16)
print("step: challenge получен", len(challenge), flush=True)
# VNC DES key: пароль до 8 байт, каждый байт с obrashennymi bitami
kb = password.encode()[:8].ljust(8, b"\x00")
rev = bytes(int(format(b, "08b")[::-1], 2) for b in kb)
enc = subprocess.run(["openssl", "enc", "-des-ecb", "-nopad", "-provider", "legacy", "-provider", "default", "-K", rev.hex()],
                     input=challenge, capture_output=True)
assert enc.returncode == 0 and len(enc.stdout) == 16, enc.stderr
ws_send(enc.stdout)
res = struct.unpack(">I", vnc_read(4))[0]
print("step: SecurityResult", res, flush=True)
assert res == 0, "SecurityResult=%d (неверный пароль?)" % res
print("E2E-VNC-OK")  # nginx token -> websockify -> x11vnc -> VNC auth прошли целиком
