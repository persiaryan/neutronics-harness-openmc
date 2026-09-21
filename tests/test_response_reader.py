"""Independent streaming fixtures, virtual delay tests, and real loopback HTTP."""
from contextlib import contextmanager
import http.client
import json
import socket
import threading
import time
import unittest
from unittest.mock import patch

from builder import relay

CREATED = b'data: {"type":"response.created","response":{"id":"fixture","status":"in_progress"}}\n\n'
COMPLETED = b'data: {"type":"response.completed","response":{"id":"fixture","status":"completed","output":[]}}\n\n'
STREAM = CREATED + COMPLETED
REQUEST = dict(model='fixture-model', stream=True, store=False, input=[dict(type='message', role='user', content=[])])


def fake_connection(connection, chunks):
    response = connection.return_value.getresponse.return_value
    response.status = 200
    response.getheader.return_value = 'text/event-stream'
    response.read1.side_effect = chunks
    return response


class ResponseReaderTests(unittest.TestCase):
    def test_completion_returns_without_an_eof_read(self):
        with patch.object(relay.http.client, 'HTTPSConnection') as connection:
            response = fake_connection(connection, [CREATED, COMPLETED, AssertionError('Must not await EOF')])
            diagnostics = {}
            self.assertEqual(relay.forward(REQUEST, {}, time.monotonic() + 5, diagnostics), STREAM)
            self.assertEqual(response.read1.call_count, 2)
            self.assertEqual(diagnostics['stop_reason'], 'response_completed')
            response.close.assert_called_once(); connection.return_value.close.assert_called_once()

    def test_post_completion_bytes_are_not_forwarded_or_used_as_output(self):
        for tail in (b'data: [DONE]\n\n', b'<html>UNTRUSTED_TRAILER</html>\n\n', STREAM,
                     b'data: {"type":"error","message":"UNTRUSTED_TRAILER"}\n\n'):
            with self.subTest(tail=tail), patch.object(relay.http.client, 'HTTPSConnection') as connection:
                fake_connection(connection, [STREAM + tail])
                diagnostics = {}
                self.assertEqual(relay.forward(REQUEST, {}, time.monotonic() + 5, diagnostics), STREAM)
                self.assertEqual(diagnostics['bytes_after_completion'], len(tail))
                self.assertNotIn('UNTRUSTED_TRAILER', str(diagnostics))
        # Whole-buffer validation remains strict; only the live response boundary changed.
        with self.assertRaises(RuntimeError):
            relay.validate_event_stream(STREAM + b'<html>UNTRUSTED_TRAILER</html>\n\n')

    def test_completion_text_in_an_output_delta_does_not_end_the_response(self):
        delta = b'data: {"type":"response.output_text.delta","delta":"response.completed"}\n\n'
        with patch.object(relay.http.client, 'HTTPSConnection') as connection:
            response = fake_connection(connection, [CREATED + delta, COMPLETED])
            self.assertEqual(relay.forward(REQUEST, {}, time.monotonic() + 5), CREATED + delta + COMPLETED)
            self.assertEqual(response.read1.call_count, 2)

    def test_fragmented_bom_unicode_and_line_endings(self):
        delta = 'data: {"type":"response.output_text.delta","delta":"é λ"}\n\n'.encode()
        for newline in (b'\n', b'\r\n', b'\r'):
            wire = b'\xef\xbb\xbf' + (CREATED + delta + COMPLETED).replace(b'\n', newline)
            for width in (1, 7, 64):
                with self.subTest(newline=newline, width=width), patch.object(relay.http.client, 'HTTPSConnection') as connection:
                    fake_connection(connection, [wire[i:i+width] for i in range(0, len(wire), width)])
                    result = relay.forward(REQUEST, {}, time.monotonic() + 5)
                    # A final CR already terminates an SSE line; a following LF can remain unread.
                    self.assertTrue(wire.startswith(result))
                    self.assertEqual(relay.validate_event_stream(result), 3)

    def test_invalid_identity_error_and_truncation_never_return_output(self):
        for wire in (CREATED + COMPLETED.replace(b'"fixture"', b'"other"'),
                     CREATED + b'data: {"type":"response.failed","message":"PRIVATE"}\n\n',
                     CREATED + b'data: {"type":"response.incomplete"}\n\n',
                     CREATED + b'data: {"type":"error"}\n\n', CREATED + COMPLETED[:-1],
                     CREATED + b'data: [DONE]\n\n', COMPLETED, CREATED + CREATED + COMPLETED):
            with self.subTest(wire=wire), patch.object(relay.http.client, 'HTTPSConnection') as connection:
                fake_connection(connection, [wire, b''])
                diagnostics = {}
                with self.assertRaises(RuntimeError) as caught:
                    relay.forward(REQUEST, {}, time.monotonic() + 5, diagnostics)
                self.assertFalse(diagnostics['completion_observed'])
                self.assertEqual(diagnostics['stream_validation'], 'failed')
                self.assertNotIn('PRIVATE', str(caught.exception) + str(diagnostics))

    def test_body_gap_over_thirty_seconds_uses_remaining_session_budget(self):
        clock = [0.0]
        with patch.object(relay.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(relay.http.client, 'HTTPSConnection') as connection:
            def read(_):
                clock[0] += 45
                return CREATED if clock[0] == 45 else COMPLETED
            response = fake_connection(connection, [])
            response.read1.side_effect = read
            self.assertEqual(relay.forward(REQUEST, {}, 300), STREAM)
            timeouts = [call.args[0] for call in connection.return_value.sock.settimeout.call_args_list]
            self.assertEqual(connection.call_args.kwargs['timeout'], 30)
            self.assertTrue(all(200 <= t <= 300 for t in timeouts), timeouts)

    def test_response_arriving_after_deadline_is_not_accepted(self):
        clock = [0.0]
        with patch.object(relay.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(relay.http.client, 'HTTPSConnection') as connection:
            def read(_):
                clock[0] = 301
                return STREAM
            response = fake_connection(connection, [])
            response.read1.side_effect = read
            diagnostics = {}
            with self.assertRaisesRegex(TimeoutError, 'wall-time budget'):
                relay.forward(REQUEST, {}, 300, diagnostics)
            self.assertEqual(diagnostics['stop_reason'], 'wall_deadline')
            self.assertFalse(diagnostics['completion_observed'])

    def test_connect_and_transport_errors_are_distinct_and_sanitized(self):
        for phase, error, reason in [('connect', TimeoutError('PRIVATE'), 'connect_timeout'),
                                     ('headers', TimeoutError('PRIVATE'), 'transport_timeout'),
                                     ('body', ConnectionResetError('PRIVATE'), 'transport_error'),
                                     ('body', http.client.IncompleteRead(b'PRIVATE'), 'transport_error')]:
            with self.subTest(phase=phase, reason=reason), patch.object(relay.http.client, 'HTTPSConnection') as connection:
                response = fake_connection(connection, [CREATED, error])
                if phase == 'connect': connection.return_value.connect.side_effect = error
                if phase == 'headers': connection.return_value.getresponse.side_effect = error
                diagnostics = {}
                with self.assertRaises((RuntimeError, TimeoutError)) as caught:
                    relay.forward(REQUEST, {}, time.monotonic() + 5, diagnostics)
                self.assertEqual(diagnostics['stop_reason'], reason)
                self.assertEqual(diagnostics['phase'], phase)
                self.assertNotIn('PRIVATE', str(caught.exception) + str(diagnostics))
                connection.return_value.close.assert_called_once()


@contextmanager
def local_response(handler):
    """One synthetic HTTP peer; never use real credentials or contact upstream."""
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0)); listener.listen(1); listener.settimeout(5)
    stop = threading.Event(); errors = []
    def server():
        try:
            with listener.accept()[0] as peer:
                peer.settimeout(5)
                header = b''
                while b'\r\n\r\n' not in header:
                    header += peer.recv(4096)
                head, body = header.split(b'\r\n\r\n', 1)
                assert b'Authorization:' not in head
                length = next(int(line.split(b':', 1)[1]) for line in head.split(b'\r\n')
                              if line.lower().startswith(b'content-length:'))
                assert length <= 1_000_000
                while len(body) < length:
                    chunk = peer.recv(4096)
                    assert chunk, 'Request body truncated'
                    body += chunk
                handler(peer, stop)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Expected when the client ends a completed or timed-out response.
        except Exception as exc:
            errors.append(exc)
    thread = threading.Thread(target=server, daemon=True); thread.start()
    connection = http.client.HTTPConnection('127.0.0.1', listener.getsockname()[1], timeout=5)
    try:
        with patch.object(relay.http.client, 'HTTPSConnection', return_value=connection):
            yield connection
    finally:
        stop.set(); connection.close(); listener.close(); thread.join(timeout=6)
        assert not thread.is_alive(), 'Local synthetic peer did not stop'
        assert not errors, errors


class LoopbackReaderTests(unittest.TestCase):
    def test_fixed_length_closing_response_can_close_its_socket_on_last_read(self):
        def handler(peer, stop):
            peer.sendall(b'HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: ' +
                         str(len(STREAM)).encode() + b'\r\n\r\n' + STREAM)
        with local_response(handler):
            self.assertEqual(relay.forward(REQUEST, {}, time.monotonic() + 3), STREAM)

    def test_completed_response_does_not_wait_for_connection_close(self):
        def handler(peer, stop):
            peer.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n' + STREAM)
            stop.wait(5)
        diagnostics = {}
        with local_response(handler) as connection:
            start = time.monotonic()
            self.assertEqual(relay.forward(REQUEST, {}, start + 3, diagnostics), STREAM)
            self.assertLess(time.monotonic() - start, 1)
            self.assertIsNone(connection.sock)
        self.assertEqual(diagnostics['stop_reason'], 'response_completed')

    def test_absolute_deadline_interrupts_connection_owned_by_response(self):
        def handler(peer, stop):
            peer.sendall(b'HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n' + CREATED)
            stop.wait(5)
        diagnostics = {}
        with local_response(handler):
            start = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, 'wall-time budget'):
                relay.forward(REQUEST, {}, start + .4, diagnostics)
            self.assertLess(time.monotonic() - start, 1.5)
        self.assertEqual(diagnostics['stop_reason'], 'wall_deadline')
        self.assertEqual(diagnostics['response_bytes_read'], len(CREATED))

    def test_absolute_deadline_interrupts_slow_header_trickle(self):
        def handler(peer, stop):
            peer.sendall(b'HTTP/1.1 200 OK\r\nX-Slow: ')
            while not stop.wait(.03): peer.sendall(b'x')
        diagnostics = {}
        with local_response(handler):
            start = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, 'wall-time budget'):
                relay.forward(REQUEST, {}, start + .4, diagnostics)
            self.assertLess(time.monotonic() - start, 1.5)
        self.assertEqual(diagnostics['stop_reason'], 'wall_deadline')
        self.assertEqual(diagnostics['phase'], 'headers')

    def test_http_chunked_payload_completes_without_last_http_chunk(self):
        def handler(peer, stop):
            peer.sendall(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Type: text/event-stream\r\n\r\n')
            for part in (CREATED, COMPLETED):
                peer.sendall(f'{len(part):x}\r\n'.encode() + part + b'\r\n')
            stop.wait(5)  # No zero chunk/EOF; Responses completion is sufficient.
        with local_response(handler):
            self.assertEqual(relay.forward(REQUEST, {}, time.monotonic() + 3), STREAM)

    def test_absolute_deadline_interrupts_incomplete_http_chunk_header(self):
        def handler(peer, stop):
            peer.sendall(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n')
            while not stop.wait(.03): peer.sendall(b'1')
        diagnostics = {}
        with local_response(handler):
            start = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, 'wall-time budget'):
                relay.forward(REQUEST, {}, start + .4, diagnostics)
            self.assertLess(time.monotonic() - start, 1.5)
        self.assertEqual(diagnostics['stop_reason'], 'wall_deadline')


if __name__ == '__main__':
    unittest.main()
