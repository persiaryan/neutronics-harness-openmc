"""Builder command: inspect_boundaries candidate.xml. No host access."""
import json
import os
from pathlib import PurePosixPath
import socket
import stat
import sys

try:  # Standalone staged command; ordinary package import is for local tests.
    from boundary_feedback import compact, encode, full_reference
except ModuleNotFoundError:
    from builder.boundary_feedback import compact, encode, full_reference


def read_candidate(name):
    path=PurePosixPath(name)
    if path.is_absolute():
        try:path=path.relative_to('/work/workspace')
        except ValueError:raise ValueError('Artifact must be inside the candidate workspace')
    if not path.parts or any(p in ('..','.') for p in path.parts):
        raise ValueError('Invalid candidate path')
    directory=os.open('/work/workspace',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    fd=None
    try:
        for part in path.parts[:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory);directory=child
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>500000:
            raise ValueError('Artifact must be a bounded regular file without links')
        with os.fdopen(fd,'rb') as stream:
            fd=None;raw=stream.read(500001)
        if len(raw)>500000:raise ValueError('Artifact byte limit')
        return raw.decode('utf-8')
    finally:
        if fd is not None:os.close(fd)
        os.close(directory)


def publish(reply):
    """Save once inside the workspace; detail reads use ordinary Python tools."""
    raw = encode(reply)
    reference = full_reference(reply)
    directory = os.open('/work/workspace', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fd = os.open(reference['path'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
        except FileExistsError:
            fd = os.open(reference['path'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                        info.st_size != len(raw) or stream.read(len(raw)+1) != raw):
                    raise ValueError('Saved result identity changed')
        else:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
    finally:
        os.close(directory)
    sys.stdout.write(encode(compact(reply)).decode())


def main():
    if len(sys.argv)!=2:raise ValueError('Usage: inspect_boundaries model.xml')
    request=dict(tool='inspect_boundaries',xml=read_candidate(sys.argv[1]))
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(300);connection.connect('/work/inspect-boundaries.sock')
        connection.sendall(json.dumps(request).encode()+b'\n')
        with connection.makefile('rb') as stream:raw=stream.readline(1800001)
    if not raw.endswith(b'\n') or len(raw)>1800000:raise ValueError('Incomplete boundary reply')
    publish(json.loads(raw))


if __name__=='__main__':
    try:main()
    except Exception:
        print(json.dumps(dict(status='indeterminate',cause='candidate_artifact_or_tool_unavailable',
                              feedback_complete=False)))
        raise SystemExit(1)
