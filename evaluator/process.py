"""Trusted process observer, sent as Python -c code; never imported by the candidate.

Run inside the existing Linux container. Separate child pipes keep candidate text
out of the observer's JSON control channel. Disabling dumpability prevents the
same-uid child opening the observer's /proc file descriptors or ptracing it.
A killed observer supplies no completion proof and must remain indeterminate.
"""
import base64
import ctypes
import json
import os
import selectors
import signal
import subprocess
import sys
import time


def observe(path, seconds, limit):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(4, 0, 0, 0, 0) != 0:  # Linux PR_SET_DUMPABLE
        raise RuntimeError('Cannot protect process observer')
    child = subprocess.Popen([sys.executable, '-I', '-B', path], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    streams = selectors.DefaultSelector()
    for number, pipe in enumerate((child.stdout, child.stderr)):
        streams.register(pipe, selectors.EVENT_READ, number)
    logs = [bytearray(), bytearray()]
    deadline, stopped = time.monotonic() + seconds, None
    while streams.get_map():
        if time.monotonic() >= deadline:
            stopped = 'timeout'
            break
        for key, _ in streams.select(min(.05, max(0, deadline - time.monotonic()))):
            chunk = os.read(key.fd, 65536)
            if not chunk:
                streams.unregister(key.fileobj)
                continue
            room = max(0, limit - sum(map(len, logs)))
            logs[key.data].extend(chunk[:room])
            if len(chunk) > room:
                stopped = 'output_limit'
                break
        if stopped:
            break
    if not stopped:
        try:
            child.wait(timeout=max(.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            stopped = 'timeout'
    if stopped:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    code = child.wait(timeout=5)
    streams.close()
    child.stdout.close(); child.stderr.close()
    return dict(format='candidate-process-v2', returncode=code, stop_reason=stopped,
                termination='signal' if code < 0 else 'exit', observer_protected=True,
                stdout_b64=base64.b64encode(logs[0]).decode(), stderr_b64=base64.b64encode(logs[1]).decode())


if __name__ == '__main__':
    print(json.dumps(observe(sys.argv[1], float(sys.argv[2]), int(sys.argv[3]))))
