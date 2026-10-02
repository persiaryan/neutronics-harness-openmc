"""Run an exploratory Codex builder in a disposable, networkless container.

Invoke from the repository root with python3 -B -m builder.run. Candidate
outputs are data: this controller never imports or executes generated Python.
"""

import argparse
import base64
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid

from builder.context import request_inventory, request_setup as observed_setup, sha256, write_json
from builder.route import CONDITIONS, BOUNDARY_CONDITIONS, SMOKE_CONDITIONS
from builder import openmc_python
from builder.relay import forward, load_auth, validate_request
from prompts.prepare import CASE_FILES
from evaluator.profiles import BOUNDARY_PROTOCOL
from observability import now, record


IMAGE = openmc_python.IMAGE_ID
LABEL = "neutronics-harness-v5.builder"
ENTRY = Path(__file__).parent / "runtime/entry.py"
MAX_FRAME = 2_000_000
MAX_LOG_BYTES = 16_000_000


def docker(*args, timeout=30):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"Docker {args[0]} failed: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def create_args(name, image):
    return ["create", "--interactive", "--name", name, "--label", LABEL + "=" + name,
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges=true", "--user", "1000:1000",
            "--pids-limit", "128", "--memory", "2g", "--cpus", "2", "--init",
            "--log-driver", "none",
            "--tmpfs", "/work:rw,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=700",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=134217728,mode=1777", image]


def verify_container(info, image):
    config, host = info["Config"], info["HostConfig"]
    checks = {
        "image_matches": info["Image"] == image,
        "network_none": host["NetworkMode"] == "none",
        "read_only_root": host["ReadonlyRootfs"] is True,
        "no_host_mounts": not info["Mounts"] and not host.get("Binds"),
        "unprivileged": not host["Privileged"] and not host.get("CapAdd") and not host.get("Devices"),
        "capabilities_dropped": host["CapDrop"] == ["ALL"],
        "no_new_privileges": "no-new-privileges=true" in host["SecurityOpt"],
        "nonroot_user": config["User"] == "1000:1000",
        "bounded_resources": host["Memory"] == 2 * 1024**3 and host["PidsLimit"] == 128
            and host["NanoCpus"] == 2_000_000_000,
        "only_ephemeral_writes": set(host["Tmpfs"]) == {"/work", "/tmp"},
        "expected_entrypoint": config["Entrypoint"] == ["python3", "-B", "/opt/builder/entry.py"],
        "no_host_namespaces": host.get("PidMode", "") == "" and host.get("IpcMode") == "private",
    }
    if not all(checks.values()):
        raise ValueError("Container boundary mismatch: " + ", ".join(k for k, v in checks.items() if not v))
    return checks


def read_frames(pipe, events):
    total = 0
    try:
        while True:
            line = pipe.readline(MAX_FRAME + 1)
            if not line:
                break
            total += len(line)
            if len(line) > MAX_FRAME or total > MAX_LOG_BYTES:
                raise ValueError("Container output exceeded its byte budget")
            frame = json.loads(line)
            if not isinstance(frame, dict):
                raise ValueError("Invalid container frame")
            events.put(frame)
    except Exception:
        events.put({"type": "protocol_error"})
    finally:
        events.put({"type": "eof"})


def send(process, value):
    process.stdin.write(json.dumps(value).encode() + b"\n")
    process.stdin.flush()


def cleanup(name):
    # Remove only this run's known container. A daemon error stays an error.
    found = docker("ps", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}")
    if found:
        docker("rm", "--force", name)
    if docker("ps", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}"):
        raise RuntimeError("Container remains after removal")


def run(output, *, case, prepared_input, model="gpt-5.6-luna", assistance='generic',
        mode='subscription', max_requests=8, wall_seconds=600, auth_path=None, responder=None,
        contract='openmc-model-factory-v1', execution_profile='factory-serial-v1',
        evaluator_protocol=BOUNDARY_PROTOCOL, smoke_data_index=None, request_setup=None, request_budget=None):
    output = Path(output)
    if mode not in {'mock', 'subscription'} or (mode == 'mock') != (responder is not None):
        raise ValueError('A local responder is required only in mock mode')
    from builder.route import request_limit
    if type(max_requests) is not int or not 1 <= max_requests <= request_limit(request_budget) or not 10 <= wall_seconds <= 600:
        raise ValueError('Budget exceeds the declared request profile or 10-600 seconds')
    if output.exists():
        raise FileExistsError('Refusing to overwrite an existing run directory')
    from builder.route import prepare, condition_prompt
    prompt, assessment_route = prepare(case, contract, execution_profile, evaluator_protocol, prepared_input)
    prompt = condition_prompt(prompt, assistance, request_budget=request_budget)
    inspect_boundaries = assistance in BOUNDARY_CONDITIONS
    smoke_enabled = assistance in SMOKE_CONDITIONS
    if smoke_enabled != (smoke_data_index is not None):
        raise ValueError('Smoke condition requires an explicit operator data index; other conditions cannot enable smoke')
    if smoke_enabled:
        from builder import smoke_tool
        from evaluator.run import data_directory
        smoke_data_index,_=data_directory(Path(smoke_data_index))
    if inspect_boundaries:
        from builder import boundary_tool
    image = IMAGE
    headers = load_auth(auth_path or Path.home() / ".codex/auth.json") if mode == "subscription" else None
    # Cleanup uncertainty from an earlier run must be reconciled first.
    if docker("ps", "-a", "--filter", "label=" + LABEL, "--format", "{{.Names}}"):
        raise RuntimeError("A prior v5 builder container remains; reconcile its lifecycle record first")
    image_info = json.loads(docker("image", "inspect", image))[0]
    openmc_python.verify_image(image_info, True)
    image_id = image_info["Id"]
    if image_id!=openmc_python.IMAGE_ID:
        raise ValueError('Builder requires the qualified pinned OpenMC authoring image')
    name = "neutronics-v5-builder-" + uuid.uuid4().hex[:16]
    output.mkdir(parents=True)
    record(output, 'authoring', 'started')
    (output / "prompt.txt").write_text(prompt)
    # Keep the exact implementation behind each run even before a Git commit.
    for source, snapshot_name in ((Path(__file__), "controller-source.py"),
                                  (Path(__file__).with_name("relay.py"), "relay-source.py"),
                                  (Path(openmc_python.__file__), "environment-source.py"),
                                  (ENTRY, "runtime-source.py")):
        (output / snapshot_name).write_bytes(source.read_bytes())
    manifest = {"format": "exploratory-codex-run-v1", "phase": "exploratory_development",
                "formal_model_comparison": False, "condition": "codex_client_without_neutronics_helpers",
                "mode": mode, "case": case, "model": model, "prompt_sha256": sha256(prompt.encode()),
                "image_id": image_id, "container_name": name, "entry_sha256": sha256(ENTRY.read_bytes()),
                "controller_sha256": sha256(Path(__file__).read_bytes()),
                "relay_sha256": sha256(Path(__file__).with_name("relay.py").read_bytes()),
                "max_requests": max_requests, "wall_seconds": wall_seconds,
                "host_candidate_execution": "not_run", "evaluator_validation": "not_run",
                "builder_tool_execution": "permitted_only_inside_container",
                "auth_enters_container": False, "host_mounts": [], "network_mode": "none"}
    manifest.update(authoring_environment=openmc_python.ENVIRONMENT,
                    delivery_contract=contract, assessment_route=assessment_route,
                    condition=CONDITIONS[assistance],
                    assistance=assistance, environment_probe_sha256=sha256(openmc_python.PROBE.encode()),
                    base_task_prompt_sha256=assessment_route['prompt_sha256'])
    if inspect_boundaries:
        manifest['boundary_tool'] = boundary_tool.identity()
    if smoke_enabled:
        manifest['smoke_tool']=smoke_tool.identity()
        manifest['smoke_data_index_sha256']=sha256(smoke_data_index.read_bytes())
    if request_setup is not None:
        manifest['required_request_setup'] = request_setup
    if request_budget is not None:
        manifest['request_budget_profile'] = request_budget
    write_json(output / "manifest.json", manifest)
    lifecycle = {"container_name": name, "state": "creating"}
    write_json(output / "lifecycle.json", lifecycle)
    process, result, count, boundary_adapter = None, {"status": "failed"}, 0, None
    smoke_adapter=None
    started = time.monotonic()
    deadline = started + wall_seconds
    try:
        container_id = docker(*create_args(name, image_id))
        lifecycle.update(container_id=container_id, state="created")
        write_json(output / "lifecycle.json", lifecycle)
        info = json.loads(docker("inspect", name))[0]
        checks = verify_container(info, image_id)
        write_json(output / "container.json", info)
        write_json(output / "container-checks.json", checks)
        process = subprocess.Popen(["docker", "start", "--attach", "--interactive", name],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        events = queue.Queue(maxsize=64)
        threading.Thread(target=read_frames, args=(process.stdout, events), daemon=True).start()
        # Docker errors are bounded separately and never interpreted as frames.
        docker_errors = []
        def read_errors():
            docker_errors.append(process.stderr.read(65536))
        error_reader = threading.Thread(target=read_errors, daemon=True)
        error_reader.start()
        ready, done = False, None
        with (output / "events.jsonl").open("w") as log:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Run wall-time budget exhausted")
                try:
                    event = events.get(timeout=min(remaining, 1))
                except queue.Empty:
                    continue
                kind = event.get("type")
                log.write(json.dumps(dict(event, observed_utc=now())) + "\n")
                log.flush()
                if kind == "ready":
                    if ready or event.get("entry_sha256") != manifest["entry_sha256"]:
                        raise ValueError("Runtime source identity mismatch or duplicate startup")
                    if not event.get("checks") or not all(event["checks"].values()):
                        raise ValueError("Runtime boundary probes failed")
                    environment = json.loads(docker('exec', name, 'python3', '-I', '-B', '-c',
                                                    openmc_python.PROBE, timeout=min(30, remaining)))
                    write_json(output / 'environment-probe.json', environment)
                    openmc_python.verify_probe(environment, True)
                    if inspect_boundaries:
                        boundary_adapter=boundary_tool.AttachedSession(container_id,output/'boundary-tool',events)
                    if smoke_enabled:
                        smoke_adapter=smoke_tool.AttachedSession(container_id,output/'smoke-tool',events,smoke_data_index)
                    ready = True
                    send(process, {"prompt": prompt, "model": model})
                elif kind == "request":
                    if not ready or done or count >= max_requests:
                        raise ValueError("Model-request budget or lifecycle violation")
                    count += 1
                    record(output, 'model_request', 'started', turn=count)
                    if event.get("id") != count:
                        raise ValueError("Nonsequential model request")
                    body = event["body"]
                    validate_request(body, model)
                    inventory = request_inventory(body)
                    if count == 1 and (inventory["skills_catalog_present"] or inventory["memory_block_present"]
                                       or len(inventory["user_texts"]) != 2
                                       or not inventory["user_texts"][0].startswith("<environment_context>")
                                       or inventory["user_texts"][-1:] != [prompt]):
                        raise ValueError("First request contains unexpected context or a changed task")
                    write_json(output / f"request-{count:02d}.json", body)
                    write_json(output / f"inventory-{count:02d}.json", inventory)
                    if request_setup is not None:
                        matched = observed_setup(body) == request_setup
                        write_json(output / f"setup-{count:02d}.json", dict(matched=matched,
                            expected_sha256=sha256(json.dumps(request_setup, sort_keys=True).encode())))
                        if not matched:
                            raise ValueError('Prepared request setup changed; request not forwarded')
                    if mode == "subscription":
                        diagnostics = {}
                        try:
                            data = forward(body, headers, deadline, diagnostics=diagnostics)
                        finally:
                            write_json(output / f"upstream-{count:02d}.json", diagnostics)
                    else:
                        data = responder(count, body)
                    (output / f"response-{count:02d}.sse").write_bytes(data)
                    record(output, 'model_request', 'completed', turn=count)
                    send(process, {"id": count, "status": 200, "data": base64.b64encode(data).decode()})
                elif kind == 'boundary_tool_request':
                    if boundary_adapter is None or done:
                        raise ValueError('Undeclared or late boundary tool request')
                    record(output, 'boundary_tool', 'started')
                    boundary_adapter.handle(event['frame'],deadline-time.monotonic())
                    record(output, 'boundary_tool', 'returned')
                elif kind == 'boundary_tool_error':
                    raise RuntimeError('Boundary tool bridge failed')
                elif kind == 'smoke_tool_request':
                    if smoke_adapter is None or done:raise ValueError('Undeclared or late smoke request')
                    record(output, 'smoke_tool', 'started')
                    smoke_adapter.handle(event['frame'],deadline-time.monotonic())
                    record(output, 'smoke_tool', 'returned')
                elif kind == 'smoke_tool_error':
                    raise RuntimeError('Smoke tool bridge failed')
                elif kind == "done":
                    if done or not ready or not count:
                        raise ValueError("Invalid completion lifecycle")
                    done = event
                    process.stdin.close()
                elif kind == "eof":
                    break
                elif kind not in {"launch", "stdout", "stderr"}:
                    raise ValueError("Invalid container protocol")
        process.wait(timeout=5)
        error_reader.join(timeout=5)
        (output / "docker-stderr.txt").write_bytes(b"".join(docker_errors))
        if not done or done.get("exit_code") != 0 or process.returncode != 0:
            raise RuntimeError("Codex did not complete successfully; inspect the retained events")
        if done.get("session_rollouts"):
            raise ValueError("Ephemeral session unexpectedly retained rollouts")
        answer = done.get("answer")
        if not isinstance(answer, str) or not answer.strip() or len(answer.encode()) > 1_000_000:
            raise ValueError("Missing or oversized final answer")
        (output / "answer.txt").write_text(answer)
        (output / "candidate.py").write_text(answer)
        result.update(status="completed", answer_sha256=sha256(answer.encode()),
                      answer_bytes=len(answer.encode()), request_count=count)
    except Exception as error:
        # Exceptions deliberately omit tokens, headers and upstream response bodies.
        result.update(error_type=type(error).__name__, error=str(error), request_count=count)
    finally:
        if smoke_adapter is not None:
            try:smoke_adapter.close()
            except Exception as error:
                result.update(status='failed',error_type=type(error).__name__,error='Smoke bridge cleanup failed')
        if boundary_adapter is not None:
            try:boundary_adapter.close()
            except Exception as error:
                result.update(status='failed',error_type=type(error).__name__,error='Boundary bridge cleanup failed')
        try:
            cleanup(name)
            lifecycle["state"] = "removed"
        except Exception as error:
            lifecycle.update(state="cleanup_uncertain", error=str(error))
            result["status"] = "cleanup_uncertain"
        if process:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            for pipe in (process.stdin, process.stdout, process.stderr):
                pipe.close()
        result.update(elapsed_seconds=round(time.monotonic() - started, 3),
                      cleanup_confirmed=lifecycle["state"] == "removed" and
                          (smoke_adapter is None or smoke_adapter.session.cleanup_confirmed),
                      host_candidate_execution="not_run", evaluator_validation="not_run")
        write_json(output / "lifecycle.json", lifecycle)
        write_json(output / "result.json", result)
        record(output, 'authoring', result['status'], cleanup_confirmed=result['cleanup_confirmed'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, choices=sorted(CASE_FILES))
    parser.add_argument('--prepared-input', required=True, type=Path)
    parser.add_argument('--assistance', choices=tuple(CONDITIONS), required=True)
    parser.add_argument('--model', default='gpt-5.6-luna')
    from builder.route import EXTENDED_REQUEST_BUDGET
    parser.add_argument('--request-budget', choices=(EXTENDED_REQUEST_BUDGET,))
    parser.add_argument('--max-requests', type=int, default=8)
    parser.add_argument('--wall-seconds', type=int, default=600)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke-data-index',type=Path)
    args = parser.parse_args()
    result = run(**vars(args))
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
