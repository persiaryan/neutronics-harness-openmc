# Subscription response reader

`relay.forward()` retains the existing fixed HTTPS destination, verified TLS,
30-second maximum connection-establishment timeout, response-byte cap and one
request without retry. After connection establishment, request/header/body I/O
uses the remaining absolute builder deadline. The default session deadline
remains 300 seconds shared by all requests, rather than restarting per response.

The relay retains the actual socket before `HTTPConnection.getresponse()` can
detach it for a connection-closing response. A watchdog interrupts active socket
operations at the absolute deadline, including slow header/chunk-header trickles.
Both the response and connection are explicitly closed on every path. Python's
platform DNS resolution is not made independently cancellable by this change;
the watchdog interrupts sockets once present and deadline checks surround I/O.

`read_response()` finds complete SSE frames incrementally. A terminal event
triggers `validate_event_stream()` on the complete received prefix: response
identity, ordering, successful completion status and output structure must pass.
Only the original bytes through the validated `response.completed` frame are
forwarded. HTTP EOF, a final HTTP chunk and an optional SSE `[DONE]` epilogue are
unnecessary. Already-read bytes after completion are counted and excluded.
Whole-buffer validation remains strict about trailing events when called directly.

This boundary follows the semantic lifecycle described in the
[OpenAI streaming guide](https://developers.openai.com/api/docs/guides/streaming-responses).
The subscription endpoint's actual compatibility is supported by retained streams
and local client qualification; the public API guide does not establish a
service-level guarantee for that endpoint.

Errors, incomplete responses, malformed frames, identity changes, truncated
completion and oversized bodies are not forwarded. Diagnostics record the reader
version, transport phase, stop reason, bytes received/forwarded, last event type
and validated-completion flag. They contain no credentials or arbitrary response
text. Timeout, HTTP/MIME rejection, invalid SSE and transport errors remain distinct.


Current regressions: tests/test_response_reader.py and tests/test_isolated_builder.py.
Historical qualification records are available through the checkpoint/archive.
