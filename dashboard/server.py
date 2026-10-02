"""Run a loopback-only, read-only operator dashboard using Python's standard library."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlsplit

from dashboard.projection import Evidence, snapshot
from dashboard.campaign import campaign, selected_roots

STATIC = Path(__file__).parent / 'static'


def make_server(roots, port=8765):
    roots = selected_roots(roots)
    cache, lock = {}, threading.Lock()

    def state(index):
        with lock:
            previous = cache.get(index)
            if previous and time.monotonic() - previous[0] < 1:
                return previous[1]
            result = snapshot(roots[index])
            cache[index] = time.monotonic(), result
            return result

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, data, mime='application/json; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            host = self.headers.get('Host')
            origin = self.headers.get('Origin')
            if host not in allowed or (origin and origin != 'http://' + host):
                return self.reply(403, b'{"error":"Local same-origin access only"}')
            url = urlsplit(self.path)
            static = {'/':'index.html', '/app.js':'app.js', '/campaign.js':'campaign.js', '/i18n.js':'i18n.js', '/style.css':'style.css'}
            if url.path in static:
                name = static[url.path]
                mime = 'text/html' if name.endswith('.html') else 'text/css' if name.endswith('.css') else 'text/javascript'
                return self.reply(200, (STATIC / name).read_bytes(), mime+'; charset=utf-8')
            if url.path == '/api/runs':
                return self.reply(200, json.dumps([dict(id=i, name=p.name) for i,p in enumerate(roots)]).encode())
            if url.path == '/api/campaign':
                try:
                    with lock:
                        previous = cache.get('campaign')
                        if previous and time.monotonic() - previous[0] < 10:
                            result = previous[1]
                        else:
                            result = campaign(roots)
                            cache['campaign'] = time.monotonic(), result
                    return self.reply(200, json.dumps(result, ensure_ascii=False, allow_nan=False).encode())
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    return self.reply(422, json.dumps(dict(error='Campaign evidence unavailable', type=type(exc).__name__)).encode())
            if url.path not in ('/api/state', '/api/artifact'):
                return self.reply(404, b'{"error":"Not found"}')
            query = parse_qs(url.query)
            try:
                index = int(query.get('run', ['0'])[0])
                if not 0 <= index < len(roots):
                    raise ValueError('Unknown run')
                result = state(index)
                if url.path == '/api/artifact':
                    path = query.get('path', [''])[0]
                    if path not in {a['path'] for a in result['artifacts']}:
                        return self.reply(404, b'{"error":"Artifact not exposed"}')
                    raw = Evidence(roots[index]).raw(path)
                    if raw is None:
                        return self.reply(404, b'{"error":"Artifact unavailable"}')
                    return self.reply(200, raw, 'text/plain; charset=utf-8')
                return self.reply(200, json.dumps(result, ensure_ascii=False, allow_nan=False).encode())
            except (ValueError, TypeError, KeyError, OSError) as exc:
                # Never turn unreadable evidence into a successful or empty run.
                self.reply(422, json.dumps(dict(error='Evidence unavailable', type=type(exc).__name__)).encode())

        def do_POST(self):
            self.reply(405, b'{"error":"Read-only dashboard"}')

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append',
                        help='Explicit run directory (repeat for local history); may not yet exist')
    parser.add_argument('--campaign', type=Path, help='JSON manifest with a runs array; paths relative to the manifest')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = make_server(selected_roots(args.run, args.campaign), args.port)
    print(f'Dashboard opérateur : http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
