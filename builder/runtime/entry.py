"""Container-side transport. Only JSON frames cross the Docker stdio pipes.

This file is part of the untrusted builder environment. The host controller
validates its output and never honors host paths or arbitrary network targets.
"""

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading


MAX_FRAME = 16_000_000
LOCK = threading.Lock()
REPLIES = queue.Queue()
VERSION = "codex-cli 0.153.4"
SKILLS = ("imagegen", "openai-docs", "plugin-creator", "skill-creator", "skill-installer")
# General coding tools remain available. All personal-context integrations are off.
DISABLED = ("memories", "apps", "plugins", "remote_plugin", "browser_use",
            "browser_use_external", "computer_use", "in_app_browser", "hooks",
            "multi_agent", "multi_agent_v2", "goals", "image_generation", "view_image",
            "tool_suggest", "skill_search", "skill_mcp_dependency_install", "shell_snapshot",
            "enable_request_compression", "workspace_dependencies", "external_agent_memory_import",
            "chronicle", "recommended_plugins", "sleep_tool")


def emit(value):
    with LOCK:
        sys.stdout.write(json.dumps(value) + "\n")
        sys.stdout.flush()


def toml(value):
    if isinstance(value, dict):
        return "{" + ", ".join(json.dumps(k) + "=" + toml(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(map(toml, value)) + "]"
    return json.dumps(value)


def read_replies():
    pending = b""
    while True:
        chunk = os.read(sys.stdin.fileno(), 65536)
        if not chunk:
            REPLIES.put(None)
            return
        pending += chunk
        if len(pending) > MAX_FRAME:
            REPLIES.put(None)
            return
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            REPLIES.put(json.loads(line))


class RelayHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_error(403)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        if (self.path != "/v1/responses" or not 0 < length <= 1_000_000
                or self.headers.get("Authorization") or self.headers.get("Content-Encoding")):
            self.send_error(403)
            return
        # Serialize requests. The controller alone owns budgets and upstream routing.
        with self.server.request_lock:
            self.server.request_number += 1
            request_id = self.server.request_number
            emit({"type": "request", "id": request_id, "body": json.loads(self.rfile.read(length))})
            reply = REPLIES.get(timeout=350)
            if not reply or reply.get("id") != request_id:
                self.send_error(502)
                return
            data = base64.b64decode(reply["data"], validate=True)
            self.send_response(reply["status"])
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


def boundary_probe():
    # Linux may expose inactive tunnel devices even with Docker network=none.
    # Test usable interfaces and routes, rather than counting sysfs entries.
    up = [name for _, name in socket.if_nameindex()
          if int(Path(f"/sys/class/net/{name}/flags").read_text().strip(), 16) & 1]
    checks = {"only_loopback_up": up == ["lo"],
              "no_ipv4_routes": len(Path("/proc/net/route").read_text().splitlines()) == 1,
              "no_external_ipv6_routes": all(line.split()[-1] == "lo"
                  for line in Path("/proc/net/ipv6_route").read_text().splitlines()),
              "no_host_home": not Path("/Users").exists(),
              "no_docker_socket": not Path("/var/run/docker.sock").exists(),
              "no_inherited_auth": not any(k in os.environ for k in ("OPENAI_API_KEY", "CODEX_ACCESS_TOKEN")),
              "fresh_state": not Path("/work/state").exists()}
    for name, address in (("internet_denied", "1.1.1.1"), ("host_gateway_denied", "192.168.65.254")):
        with socket.socket() as sock:
            sock.settimeout(1)
            checks[name] = sock.connect_ex((address, 443)) != 0
    Path("/work/write-probe").write_text("SYNTHETIC_WRITE_OK")
    checks["workspace_writable"] = Path("/work/write-probe").read_text() == "SYNTHETIC_WRITE_OK"
    Path("/work/write-probe").unlink()
    return checks


def command(model, port):
    args = ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
            "--skip-git-repo-check", "--strict-config", "--json", "-m", model,
            "--sandbox", "danger-full-access"]
    config = {
        "model_provider": "isolated_relay",
        "model_providers.isolated_relay": {
            "name": "isolated_relay", "base_url": f"http://127.0.0.1:{port}/v1",
            "wire_api": "responses", "requires_openai_auth": False, "supports_websockets": False,
            "request_max_retries": 0, "stream_max_retries": 0, "stream_idle_timeout_ms": 350000},
        "model_catalog_json": "/work/catalog.json", "cli_auth_credentials_store": "ephemeral",
        "web_search": "disabled", "approval_policy": "never", "project_doc_max_bytes": 0,
        "check_for_update_on_startup": False, "memories.use_memories": False,
        "memories.generate_memories": False,
        "skills.config": [{"path": f"/work/state/skills/.system/{name}/SKILL.md", "enabled": False}
                          for name in SKILLS],
    }
    for key, value in config.items():
        args += ["-c", key + "=" + toml(value)]
    for name in DISABLED:
        args += ["--disable", name]
    return args + ["-o", "/work/answer.txt", "-"]


def relay_log(pipe, kind):
    for line in iter(pipe.readline, ""):
        emit({"type": kind, "text": line})


def main():
    checks = boundary_probe()
    version = subprocess.check_output(["codex", "--version"], text=True).strip()
    checks["pinned_cli"] = version == VERSION
    emit({"type": "ready", "checks": checks, "version": version,
          "entry_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    if not all(checks.values()):
        return 1
    job = json.loads(sys.stdin.buffer.readline(1_000_001))
    for path in ("/work/home", "/work/state", "/work/workspace"):
        Path(path).mkdir()
    catalog = subprocess.check_output(["codex", "debug", "models", "--bundled"], text=True)
    Path("/work/catalog.json").write_text(catalog)
    server = ThreadingHTTPServer(("127.0.0.1", 0), RelayHandler)
    server.request_lock, server.request_number = threading.Lock(), 0
    threading.Thread(target=server.serve_forever, daemon=True).start()
    reply_reader = threading.Thread(target=read_replies, daemon=True)
    reply_reader.start()
    args = command(job["model"], server.server_port)
    emit({"type": "launch", "command": args, "catalog_sha256": hashlib.sha256(catalog.encode()).hexdigest()})
    process = subprocess.Popen(args, cwd="/work/workspace", stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    threads = [threading.Thread(target=relay_log, args=(pipe, kind), daemon=True)
               for pipe, kind in ((process.stdout, "stdout"), (process.stderr, "stderr"))]
    for thread in threads:
        thread.start()
    process.stdin.write(job["prompt"])
    process.stdin.close()
    code = process.wait()
    for thread in threads:
        thread.join(timeout=5)
    server.shutdown()
    server.server_close()
    answer = Path("/work/answer.txt")
    # This is untrusted output, never a host path or an archive to extract.
    with answer.open("rb") if answer.is_file() else open(os.devnull, "rb") as file:
        raw = file.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Candidate output exceeds limit")
    emit({"type": "done", "exit_code": code, "answer": raw.decode(),
          "session_rollouts": [str(p.relative_to('/work/state')) for p in Path('/work/state').rglob('rollout-*')]})
    reply_reader.join(timeout=5)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
