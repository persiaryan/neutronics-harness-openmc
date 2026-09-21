"""Independent boundary and lifecycle tests; no Docker or paid requests needed."""

import base64
import io
import json
from pathlib import Path
import queue
import tempfile
import time
import unittest
from unittest.mock import patch

from builder import relay
from tests.fixtures import responses
from builder import run as launcher


def request():
    return {"model": "test-model", "store": False, "stream": True, "input": [
        {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "<environment_context>synthetic</environment_context>"}]},
        {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "synthetic task"}]}]}


def event_stream():
    # Independent wire fixture: do not derive parser expectations from mock_response().
    return (b'event: response.created\n'
            b'data: {"type":"response.created","response":{"id":"resp_test","status":"in_progress"}}\n\n'
            b'event: response.completed\n'
            b'data: {"type":"response.completed","response":{"id":"resp_test","status":"completed",'
            b'"output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"OK"}]}]}}\n\n')


def container():
    return {"Image": "sha256:fixture", "Mounts": [],
            "Config": {"User": "1000:1000", "Entrypoint": ["python3", "-B", "/opt/builder/entry.py"]},
            "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "Binds": [],
                "Privileged": False, "CapAdd": [], "Devices": [], "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges=true"], "Memory": 2147483648, "PidsLimit": 128,
                "NanoCpus": 2000000000, "Tmpfs": {"/work": "rw", "/tmp": "rw"},
                "PidMode": "", "IpcMode": "private"}}


class RelayTests(unittest.TestCase):
    def test_explicit_local_function_tools_are_allowed_in_both_formats(self):
        body = request()
        body["tools"] = [{"type": "function", "name": "local_function"}]
        body["input"].insert(0, {"type": "additional_tools", "tools": [{"type": "namespace",
            "name": "functions", "tools": [{"type": "custom", "name": "exec"}]}]})
        relay.validate_request(body, "test-model")

    def test_history_retrieval_and_redirect_fields_are_rejected(self):
        for key in ("previous_response_id", "conversation", "url", "background"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                relay.validate_request({**request(), key: "forbidden"}, "test-model")

    def test_hosted_tools_and_remote_files_are_rejected(self):
        for kind in ("web_search", "file_search", "mcp", "future_tool"):
            body = request()
            body["input"].insert(0, {"type": "additional_tools", "tools": [{"type": kind}]})
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                relay.validate_request(body, "test-model")
        for kind in ("input_file", "input_image"):
            body = request()
            body["input"][0]["content"].append({"type": kind, "file_url": "https://example.invalid/private"})
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                relay.validate_request(body, "test-model")

    def test_wrong_model_storage_and_oversized_input_fail_closed(self):
        for change in ({"model": "other-model"}, {"store": True}, {"stream": False},
                       {"input": []}, {"instructions": "x" * 1_000_001}):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                relay.validate_request({**request(), **change}, "test-model")

    def test_mock_tool_requires_a_successful_output_not_an_echoed_marker(self):
        body = {"input": [{"type": "custom_tool_call_output", "output": [
            {"type": "input_text", "text": json.dumps({"exit_code": 0, "output": "ISOLATED_TOOL_OK\n"})}]}]}
        self.assertTrue(responses.mock_tool_succeeded(body))
        body["input"][0]["output"][0]["text"] = json.dumps({"exit_code": 1, "output": "ISOLATED_TOOL_OK"})
        self.assertFalse(responses.mock_tool_succeeded(body))
        body["input"][0]["output"] = "Error running print('ISOLATED_TOOL_OK')"
        self.assertFalse(responses.mock_tool_succeeded(body))

    def test_auth_reads_only_required_fields_and_rejects_expiry(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic-auth.json"
            def auth(expiry):
                claims = base64.urlsafe_b64encode(json.dumps({"exp": expiry}).encode()).decode().rstrip("=")
                return {"auth_mode": "chatgpt", "tokens": {"access_token": "fixture." + claims + ".fixture",
                    "account_id": "synthetic-account", "refresh_token": "DO_NOT_FORWARD_REFRESH"}}
            path.write_text(json.dumps(auth(time.time() + 3600)))
            headers = relay.load_auth(path)
            self.assertEqual(set(headers), {"Authorization", "ChatGPT-Account-Id"})
            self.assertNotIn("DO_NOT_FORWARD_REFRESH", str(headers))
            path.write_text(json.dumps(auth(time.time() - 1)))
            with self.assertRaisesRegex(ValueError, "expired"):
                relay.load_auth(path)

    def test_non_200_responses_are_not_followed_or_forwarded(self):
        for status in (301, 401, 429, 500):
            with self.subTest(status=status), patch.object(relay.http.client, "HTTPSConnection") as connection:
                response = connection.return_value.getresponse.return_value
                response.status = status
                response.getheader.return_value = "application/json"
                with self.assertRaisesRegex(RuntimeError, str(status)):
                    relay.forward(request(), {"Authorization": "Bearer SYNTHETIC"}, time.monotonic() + 5)
                response.read1.assert_not_called()
                connection.return_value.close.assert_called_once()

    def test_successful_forward_uses_only_fixed_endpoint_and_bounds_response(self):
        with patch.object(relay.http.client, "HTTPSConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.getheader.return_value = "text/event-stream"
            response.read1.side_effect = [event_stream()[:37], event_stream()[37:], b""]
            data = relay.forward(request(), {"Authorization": "SYNTHETIC"}, time.monotonic() + 5)
            self.assertEqual(data, event_stream())
            self.assertEqual(connection.call_args.args[0], "chatgpt.com")
            self.assertEqual(connection.return_value.request.call_args.args[:2],
                             ("POST", "/backend-api/codex/responses"))
            response.read1.side_effect = [b"x" * (relay.MAX_RESPONSE_BYTES + 1)]
            with self.assertRaisesRegex(ValueError, "byte budget"):
                relay.forward(request(), {}, time.monotonic() + 5)

    def test_sse_media_type_is_case_insensitive_and_allows_parameters(self):
        with patch.object(relay.http.client, "HTTPSConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.getheader.return_value = " Text/Event-Stream ; charset=utf-8"
            response.read1.side_effect = [event_stream(), b""]
            self.assertEqual(relay.forward(request(), {}, time.monotonic() + 5),
                             event_stream())

    def test_unexpected_content_type_is_reported_without_reading_body(self):
        for content_type, expected in (("text/html; charset=utf-8", "text/html"),
                                       ("application/json", "application/json"),
                                       ("application/text/event-stream", "<invalid>"),
                                       ("text/event-stream-extra", "text/event-stream-extra"),
                                       ("text/plain; token=SYNTHETIC_SECRET", "text/plain"),
                                       ("text/html\r\nSYNTHETIC_SECRET", "<invalid>"),
                                       ("x" * 128 + "/json", "<invalid>")):
            with self.subTest(content_type=content_type), \
                    patch.object(relay.http.client, "HTTPSConnection") as connection:
                response = connection.return_value.getresponse.return_value
                response.status = 200
                response.getheader.return_value = content_type
                with self.assertRaises(RuntimeError) as caught:
                    relay.forward(request(), {}, time.monotonic() + 5)
                self.assertIn("HTTP 200, Content-Type: " + expected + ";", str(caught.exception))
                self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception))
                response.read1.assert_not_called()
                connection.return_value.close.assert_called_once()

    def test_missing_header_passes_only_after_complete_stream_validation(self):
        with patch.object(relay.http.client, "HTTPSConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.getheader.return_value = ""
            response.read1.side_effect = [event_stream(), b""]
            diagnostics = {}
            self.assertEqual(relay.forward(request(), {}, time.monotonic() + 5, diagnostics), event_stream())
            self.assertEqual(diagnostics, {"http_status": 200, "content_type": "<missing>",
                "response_bytes_read": len(event_stream()), "stream_validation": "passed",
                "event_count": 2, "missing_content_type_accepted": True,
                "reader_version": relay.READER_VERSION, "completion_observed": True,
                "phase": "finished", "stop_reason": "response_completed", "last_event_type": "response.completed",
                "response_bytes_forwarded": len(event_stream()), "bytes_after_completion": 0})

    def test_invalid_bodies_fail_with_or_without_an_sse_header(self):
        for media_type in ("", "text/event-stream"):
            for data, message in ((b"", "empty"), (b"<html>SYNTHETIC_SECRET</html>", "HTML/XML"),
                                  (b'{"error":"SYNTHETIC_SECRET"}', "body is JSON"),
                                  (b"\xff", "UTF-8"), (b"data: {}", "unterminated"),
                                  (b"data: INVALID_JSON\n\n", "not valid JSON"),
                                  (b"SYNTHETIC_SECRET\n\n", "invalid SSE field"),
                                  (event_stream().split(b"event: response.completed")[0], "without response.completed")):
                with self.subTest(media_type=media_type, message=message), \
                        patch.object(relay.http.client, "HTTPSConnection") as connection:
                    response = connection.return_value.getresponse.return_value
                    response.status = 200
                    response.getheader.return_value = media_type
                    response.read1.side_effect = [data, b""] if data else [b""]
                    diagnostics = {}
                    with self.assertRaisesRegex(RuntimeError, message) as caught:
                        relay.forward(request(), {}, time.monotonic() + 5, diagnostics)
                    self.assertEqual(diagnostics["stream_validation"], "failed")
                    self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception) + str(diagnostics))
                    connection.return_value.close.assert_called_once()

    def test_stream_rejects_error_identity_and_completion_violations(self):
        created = event_stream().split(b"event: response.completed")[0]
        cases = [event_stream().replace(b'"id":"resp_test","status":"completed"',
                                        b'"id":"resp_other","status":"completed"'),
                 event_stream().replace(b'"status":"completed"', b'"status":"in_progress"'),
                 event_stream().replace(b'"output":[', b'"wrong_key":['),
                 event_stream().replace(b"event: response.completed", b"event: response.failed"),
                 event_stream() + event_stream(), created + event_stream(),
                 b'data: {"type":"response.completed","response":{"id":"resp_test","status":"completed","output":[]}}\n\n']
        for kind in ("error", "response.failed", "response.incomplete"):
            cases.append(created + b"data: " + json.dumps({"type": kind,
                         "message": "SYNTHETIC_SECRET"}).encode() + b"\n\n")
        for data in cases:
            with self.subTest(data=data), self.assertRaises(RuntimeError) as caught:
                relay.validate_event_stream(data)
            self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception))

    def test_stream_accepts_sse_comments_data_only_events_and_multiline_json(self):
        stream = event_stream().replace(b"event: response.created\n", b": keepalive\n")
        stream = stream.replace(b"event: response.completed\n", b"id: 2\nretry: 1000\n")
        stream = stream.replace(b'"response":{', b'\ndata: "response":{')
        stream = b"\xef\xbb\xbf" + stream.replace(b"\n", b"\r\n") + b"data: [DONE]\r\n\r\n"
        self.assertEqual(relay.validate_event_stream(stream), 2)

    def test_real_http_parser_preserves_a_stream_without_content_type(self):
        class Socket:
            def makefile(self, *args):
                return io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: " +
                                  str(len(event_stream())).encode() + b"\r\n\r\n" + event_stream())
        with patch.object(relay.http.client, "HTTPSConnection") as connection:
            response = relay.http.client.HTTPResponse(Socket())
            response.begin()
            connection.return_value.getresponse.return_value = response
            diagnostics = {}
            self.assertEqual(relay.forward(request(), {}, time.monotonic() + 5, diagnostics), event_stream())
            self.assertTrue(diagnostics["missing_content_type_accepted"])

    def test_expired_deadline_stops_before_any_network_connection(self):
        with patch.object(relay.http.client, "HTTPSConnection") as connection:
            with self.assertRaises(TimeoutError):
                relay.forward(request(), {}, time.monotonic() - 1)
            connection.assert_not_called()


class ContainerBoundaryTests(unittest.TestCase):
    def test_mount_network_privilege_and_resource_changes_are_rejected(self):
        self.assertTrue(all(launcher.verify_container(container(), "sha256:fixture").values()))
        changes = [("NetworkMode", "host"), ("ReadonlyRootfs", False), ("Binds", ["/Users:/Users"]),
                   ("Privileged", True), ("CapAdd", ["SYS_ADMIN"]), ("CapDrop", []),
                   ("SecurityOpt", []), ("Memory", 0), ("PidsLimit", 0), ("NanoCpus", 0),
                   ("PidMode", "host"), ("IpcMode", "host")]
        for key, value in changes:
            info = container()
            info["HostConfig"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                launcher.verify_container(info, "sha256:fixture")
        info = container()
        info["Mounts"] = [{"Source": "/private/reference"}]
        with self.assertRaises(ValueError):
            launcher.verify_container(info, "sha256:fixture")

    def test_oversized_and_malformed_protocol_stops(self):
        for data in (b"not json\n", b"x" * (launcher.MAX_FRAME + 1), b"[]\n"):
            events = queue.Queue()
            launcher.read_frames(io.BytesIO(data), events)
            self.assertEqual(events.get(), {"type": "protocol_error"})
            self.assertEqual(events.get(), {"type": "eof"})



class BuilderDouble(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "run"
        self.calls, self.present = [], False
        self.patcher = patch.object(launcher, "docker", side_effect=self.docker)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def docker(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == "ps":
            return "fixture-container" if self.present else ""
        if args[:2] == ("image", "inspect"):
            label = ({launcher.openmc_python.LABEL: launcher.openmc_python.ENVIRONMENT}
                     if args[2] == launcher.IMAGE else {})
            return json.dumps([{"Id": launcher.IMAGE, "Config": {"Labels": label}}])
        if args[0] == "exec":
            enabled = any(c[:3] == ('image', 'inspect', launcher.IMAGE) for c in self.calls)
            return json.dumps({'openmc_version': '0.15.3' if enabled else None,
                               'openmc_init_sha256': 'fixture-hash' if enabled else None,
                               'native_openmc_present': False, 'data_directory_present': False,
                               'cross_sections_configured': False})
        if args[0] == "create":
            self.present = True
            return "container-id"
        if args[0] == "inspect":
            info=container(); info['Image']=launcher.IMAGE; info['Config']['Labels']={launcher.openmc_python.LABEL:launcher.openmc_python.ENVIRONMENT}; return json.dumps([info])
        if args[0] == "rm":
            self.present = False
            return "removed"
        raise AssertionError(args)

    def fake_process(self, body=None, answer="BUILDER_ISOLATION_OK", duplicate_request=False):
        frames = [{"type": "ready", "entry_sha256": launcher.sha256(launcher.ENTRY.read_bytes()),
                   "checks": {"synthetic_boundary": True}},
                  {"type": "request", "id": 1, "body": body or request()}]
        if duplicate_request:
            frames.append({"type": "request", "id": 2, "body": body or request()})
        frames.append({"type": "done", "exit_code": 0, "answer": answer, "session_rollouts": []})
        class Process:
            stdin = io.BytesIO()
            stdout = io.BytesIO("".join(json.dumps(f) + "\n" for f in frames).encode())
            stderr = io.BytesIO()
            returncode = 0
            def wait(self, timeout=None):
                return self.returncode
        return Process()

















if __name__ == "__main__":
    unittest.main()
