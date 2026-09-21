"""Host-only, bounded relay to one Codex subscription endpoint.

Credentials never enter the builder. The relay has no general proxy, file-read,
conversation retrieval, or host-command operation. Do not log auth headers.
"""

import base64
import http.client
import json
from pathlib import Path
import re
import shlex
import socket
import ssl
import threading
import time


MAX_REQUEST_BYTES = 1_000_000
MAX_RESPONSE_BYTES = 8_000_000
UPSTREAM_HOST = "chatgpt.com"
UPSTREAM_PATH = "/backend-api/codex/responses"
REQUEST_KEYS = {"model", "instructions", "input", "tools", "tool_choice", "parallel_tool_calls",
                "reasoning", "store", "stream", "include", "prompt_cache_key", "text", "client_metadata"}
INPUT_TYPES = {"message", "additional_tools", "reasoning", "function_call", "function_call_output",
               "custom_tool_call", "custom_tool_call_output"}
READER_VERSION = "responses-completion-deadline-v1"
# A CRLF is one line ending, never two. Accept the existing LF/CR/CRLF profile.
FRAME_END = re.compile(rb"(?:\r\n|\r(?!\n)|\n)(?:\r\n|\r(?!\n)|\n)")


def event_frame(block):
    """Parse one decoded SSE frame without returning its contents in errors."""
    event_name, values = None, []
    for line in block.split("\n"):
        if not line or line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if not separator or field not in {"event", "data", "id", "retry"}:
            raise RuntimeError("Upstream event stream contains an invalid SSE field")
        if field == "event":
            if event_name is not None:
                raise RuntimeError("Upstream event frame repeats its event field")
            event_name = value
        elif field == "data":
            values.append(value)
    if not values:
        if event_name is not None:
            raise RuntimeError("Upstream event frame has no data")
        return None
    payload = "\n".join(values)
    if payload == "[DONE]" and event_name is None:
        return "[DONE]"
    try:
        event = json.loads(payload)
    except (json.JSONDecodeError, RecursionError):
        raise RuntimeError("Upstream event data is not valid JSON") from None
    kind = event.get("type") if isinstance(event, dict) else None
    if not isinstance(kind, str) or (event_name is not None and event_name != kind):
        raise RuntimeError("Upstream event type is missing or inconsistent")
    return event


def validate_request(body, model):
    if not isinstance(body, dict) or set(body) - REQUEST_KEYS:
        raise ValueError("Unsupported request fields (history/retrieval operations are not allowed)")
    if body.get("model") != model or body.get("store") is not False or body.get("stream") is not True:
        raise ValueError("Request must use the selected model, store=false and stream=true")
    if len(json.dumps(body).encode()) > MAX_REQUEST_BYTES:
        raise ValueError("Request exceeds byte budget")
    if not isinstance(body.get("input"), list) or not body["input"]:
        raise ValueError("Expected explicit conversation input")

    def tools(nodes):
        if not isinstance(nodes, list):
            raise ValueError("Malformed tool list")
        for node in nodes:
            if not isinstance(node, dict) or node.get("type") not in {"function", "custom", "namespace"}:
                raise ValueError("Hosted tools, connectors and unknown tool types are prohibited")
            if "tools" in node:
                tools(node["tools"])

    def content(node):
        if isinstance(node, dict):
            if node.get("type") in {"input_file", "input_image", "image_url", "file", "file_search",
                                     "web_search", "web_search_preview", "mcp", "computer_use"}:
                raise ValueError("Remote files, images and hosted capabilities are prohibited")
            for value in node.values():
                content(value)
        elif isinstance(node, list):
            for value in node:
                content(value)

    tools(body.get("tools", []))
    for item in body["input"]:
        if not isinstance(item, dict) or item.get("type") not in INPUT_TYPES:
            raise ValueError("Unsupported input item; implicit history is prohibited")
        if item["type"] == "additional_tools":
            tools(item.get("tools", []))
        parts = item.get("content") if item["type"] == "message" else None
        if item["type"] in {"function_call_output", "custom_tool_call_output"}:
            parts = item.get("output")
            if isinstance(parts, str):
                parts = None
        if parts is not None:
            if not isinstance(parts, list) or any(not isinstance(part, dict)
                    or part.get("type") not in {"input_text", "output_text"}
                    or not isinstance(part.get("text"), str) for part in parts):
                raise ValueError("Only text content and local tool output are permitted")
    content(body)


def load_auth(path):
    """Read the existing login cache without changing it or returning identity data."""
    auth = json.loads(Path(path).read_text())
    if auth.get("auth_mode") != "chatgpt":
        raise ValueError("A ChatGPT Codex login is required; API keys are not used by this launcher")
    tokens = auth.get("tokens", {})
    token, account = tokens.get("access_token"), tokens.get("account_id")
    if not isinstance(token, str) or not token or not isinstance(account, str) or not account:
        raise ValueError("Missing subscription credentials; run codex login")
    try:
        encoded = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if claims["exp"] < time.time() + 60:
            raise ValueError("Subscription token expired; refresh the login with codex login")
    except (IndexError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("Unrecognized login token; refresh the login with codex login") from error
    if any(c in token + account for c in "\r\n"):
        raise ValueError("Invalid authentication header")
    return {"Authorization": "Bearer " + token, "ChatGPT-Account-Id": account}


def validate_event_stream(data):
    """Check a buffered Responses stream without logging its contents or changing it."""
    try:
        stream = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        raise RuntimeError("Upstream body is not a UTF-8 event stream") from None
    if not stream.strip():
        raise RuntimeError("Upstream body is empty; expected Responses events")
    if stream.lstrip().startswith("<"):
        raise RuntimeError("Upstream body is HTML/XML, not Responses events")
    if stream.lstrip().startswith(("{", "[")):
        raise RuntimeError("Upstream body is JSON, not a Responses event stream")
    blocks = stream.split("\n\n")
    if blocks[-1].strip():
        raise RuntimeError("Upstream event stream has an unterminated frame")
    response_id, completed, count = None, False, 0
    for block in blocks[:-1]:
        event = event_frame(block)
        if event is None or (event == "[DONE]" and completed):
            continue
        if event == "[DONE]":
            raise RuntimeError("Upstream stream ended without response.completed")
        kind = event["type"]
        if kind in {"error", "response.failed", "response.incomplete"}:
            raise RuntimeError(f"Upstream reported {kind}; response body not forwarded")
        if completed or not re.fullmatch(r"response\.[a-z0-9_.]{1,80}", kind):
            raise RuntimeError("Unexpected event in upstream Responses stream")
        response = event.get("response")
        if response_id is None:
            if (kind != "response.created" or not isinstance(response, dict)
                    or not isinstance(response.get("id"), str) or not response["id"]):
                raise RuntimeError("Upstream stream does not start with response.created")
            response_id = response["id"]
        elif kind == "response.created":
            raise RuntimeError("Upstream stream repeats response.created")
        if response is not None and (not isinstance(response, dict) or response.get("id") != response_id):
            raise RuntimeError("Upstream stream changes response identity")
        if kind == "response.completed":
            if (not isinstance(response, dict) or response.get("status") != "completed"
                    or response.get("error") is not None or not isinstance(response.get("output"), list)):
                raise RuntimeError("Upstream completion is malformed")
            completed = True
        count += 1
    if not completed:
        raise RuntimeError("Upstream stream ended without response.completed")
    return count


def read_response(response, budget, diagnostics):
    """Buffer only bounded bytes; validate the exact prefix ending at completion.

    No partial output reaches the builder. Bytes after the terminal event are
    neither needed nor forwarded, including an optional SSE [DONE] epilogue.
    """
    data, cursor = bytearray(), 0
    while True:
        budget(set_timeout=True)
        chunk = response.read1(65536)
        budget()
        if not chunk:
            diagnostics['stop_reason'] = 'eof_before_completion'
            diagnostics['stream_validation'] = 'failed'
            validate_event_stream(bytes(data))  # Preserve the precise, sanitized EOF error.
            raise RuntimeError('Upstream stream ended without response.completed')
        data.extend(chunk)
        diagnostics['response_bytes_read'] = len(data)
        if len(data) > MAX_RESPONSE_BYTES:
            diagnostics['stop_reason'] = 'response_byte_limit'
            raise ValueError('Upstream response exceeds byte budget')
        while match := FRAME_END.search(data, cursor):
            try:
                block = bytes(data[cursor:match.start()]).decode('utf-8-sig' if cursor == 0 else 'utf-8')
            except UnicodeDecodeError:
                diagnostics['stream_validation'] = 'failed'
                raise RuntimeError('Upstream body is not a UTF-8 event stream') from None
            block = block.replace('\r\n', '\n').replace('\r', '\n')
            event = event_frame(block)
            cursor = match.end()
            if event is None:
                continue
            if event == '[DONE]':
                diagnostics['stream_validation'] = 'failed'
                raise RuntimeError('Upstream stream ended without response.completed')
            diagnostics['last_event_type'] = event['type'] if re.fullmatch(r'(?:response\.[a-z0-9_.]{1,80}|error)', event['type']) else '<invalid>'
            if event['type'] in {'response.completed', 'response.failed', 'response.incomplete', 'error'}:
                prefix = bytes(data[:cursor])
                diagnostics['stream_validation'] = 'failed'
                count = validate_event_stream(prefix)
                budget()
                diagnostics.update(stream_validation='passed', event_count=count,
                                   completion_observed=True, stop_reason='response_completed',
                                   response_bytes_forwarded=len(prefix), bytes_after_completion=len(data) - len(prefix))
                return prefix


def forward(body, headers, deadline, diagnostics=None):
    """One request, one absolute deadline, and one validated completed response."""
    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics.update(reader_version=READER_VERSION, response_bytes_read=0, stream_validation="not_run",
                       completion_observed=False, phase='connect', stop_reason=None)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        diagnostics['stop_reason'] = 'wall_deadline'
        raise TimeoutError("Run wall-time budget exhausted")
    connection = http.client.HTTPSConnection(UPSTREAM_HOST, context=ssl.create_default_context(),
                                              timeout=min(30, remaining))
    response, read_socket = None, None
    expired = threading.Event()

    def expire():
        # shutdown interrupts reads even when HTTPResponse owns the socket after
        # getresponse() detached it from connection.sock (will_close responses).
        expired.set()
        for sock in (read_socket, connection.sock):
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def budget(*, set_timeout=False):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or expired.is_set():
            raise TimeoutError('Run wall-time budget exhausted')
        if set_timeout and read_socket is not None:
            read_socket.settimeout(remaining)

    # A watchdog also bounds slow trickles inside HTTP header/chunk parsing,
    # where one high-level read can perform several underlying socket reads.
    timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
    timer.daemon = True
    timer.start()
    try:
        connection.connect()
        read_socket = connection.sock
        diagnostics['phase'] = 'request'
        budget(set_timeout=True)
        connection.request("POST", UPSTREAM_PATH, body=json.dumps(body).encode(), headers={
            **headers, "Content-Type": "application/json", "Accept": "text/event-stream",
            "originator": "codex_cli_rs", "User-Agent": "codex_cli_rs/0.153.4"})
        diagnostics['phase'] = 'headers'
        budget(set_timeout=True)
        response = connection.getresponse()
        budget()
        # MIME types are case-insensitive; parameters do not change the type.
        # Retain only a bounded media type, never cookies, auth headers or bodies.
        media_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        if not media_type:
            media_type = "<missing>"
        elif len(media_type) > 127 or not re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", media_type):
            media_type = "<invalid>"
        diagnostics.update(http_status=response.status, content_type=media_type)
        # Never relay an auth error, redirect body, or arbitrary upstream HTML to the builder.
        if response.status != 200:
            diagnostics['stop_reason'] = 'http_status'
            raise RuntimeError(f"Subscription endpoint returned HTTP {response.status} "
                               f"(Content-Type: {media_type}); no automatic retry")
        if media_type not in {"text/event-stream", "<missing>"}:
            diagnostics['stop_reason'] = 'content_type'
            raise RuntimeError(f"Unexpected upstream content type: HTTP 200, Content-Type: {media_type}; "
                               "expected text/event-stream; response body not read or forwarded")
        diagnostics['phase'] = 'body'
        try:
            data = read_response(response, budget, diagnostics)
        except RuntimeError as error:
            diagnostics['stream_validation'] = 'failed'
            diagnostics['stop_reason'] = diagnostics['stop_reason'] or 'invalid_stream'
            raise RuntimeError(f"HTTP 200, Content-Type: {media_type}; {error}") from None
        diagnostics.update(phase='finished', missing_content_type_accepted=media_type == "<missing>")
        return data
    except TimeoutError:
        if expired.is_set() or time.monotonic() >= deadline:
            diagnostics['stop_reason'] = 'wall_deadline'
            raise TimeoutError('Run wall-time budget exhausted during upstream ' + diagnostics['phase']) from None
        diagnostics['stop_reason'] = 'connect_timeout' if diagnostics['phase'] == 'connect' else 'transport_timeout'
        raise TimeoutError('Upstream transport timed out during ' + diagnostics['phase']) from None
    except (OSError, http.client.HTTPException) as error:
        if expired.is_set() or time.monotonic() >= deadline:
            diagnostics['stop_reason'] = 'wall_deadline'
            raise TimeoutError('Run wall-time budget exhausted during upstream ' + diagnostics['phase']) from None
        diagnostics.update(stop_reason='transport_error', transport_error_type=type(error).__name__)
        raise RuntimeError('Upstream transport failed during ' + diagnostics['phase']) from None
    finally:
        timer.cancel()
        timer.join()
        if response is not None:
            response.close()
        connection.close()
