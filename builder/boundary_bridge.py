"""Injected into one builder container. Bytes only; no host paths or sockets."""
import json
import os
import socket
import sys

server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
server.bind('/work/inspect-boundaries.sock');os.chmod('/work/inspect-boundaries.sock',0o600)
server.listen(1)
print(json.dumps(dict(type='boundary_ready')),flush=True)
number=0
while True:
    connection,_=server.accept()
    with connection:
        connection.settimeout(300)
        with connection.makefile('rb') as stream:
            raw=stream.readline(700001)
        if len(raw)>700000 or not raw.endswith(b'\n'):
            connection.sendall(b'{"status":"indeterminate","cause":"invalid_frame"}\n');continue
        try:request=json.loads(raw)
        except Exception:
            connection.sendall(b'{"status":"indeterminate","cause":"invalid_json"}\n');continue
        number+=1
        print(json.dumps(dict(id=number,request=request)),flush=True)
        reply=sys.stdin.buffer.readline(1800001)
        if not reply:break
        value=json.loads(reply)
        if value['id']!=number:raise RuntimeError('Unexpected tool reply sequence')
        connection.sendall(json.dumps(value['response']).encode()+b'\n')
