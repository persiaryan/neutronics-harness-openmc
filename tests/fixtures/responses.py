"""Fixed offline wire responses; no network or provider access."""
import json


def mock_response(tool=False, command=None):
    if tool or command is not None:
        probe = ("from pathlib import Path; import socket, os; "
                 "assert not Path('/Users').exists(); "
                 "assert not Path('/var/run/docker.sock').exists(); "
                 "assert not Path('/work/state/auth.json').exists(); "
                 "assert 'OPENAI_API_KEY' not in os.environ; "
                 "s=socket.socket(); s.settimeout(1); "
                 "assert s.connect_ex(('1.1.1.1',443)) != 0; s.close(); "
                 "p=Path('/work/workspace/tool-probe'); p.write_text('ok'); "
                 "assert p.read_text()=='ok'; p.unlink(); print('ISOLATED_TOOL_OK')")
        code = "text(await tools.exec_command(" + json.dumps({"cmd": command or "python3 -c " + shlex.quote(probe),
                                                              **({'yield_time_ms':30000} if command else {})}) + "));"
        item = {"id": "tool_mock", "type": "custom_tool_call", "call_id": "call_mock",
                "name": "exec", "namespace": "functions", "status": "completed",
                "input": code}
    else:
        item = {"id": "msg_mock", "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": "BUILDER_ISOLATION_OK", "annotations": []}]}
    events = [
        ("response.created", {"response": {"id": "resp_mock", "status": "in_progress", "output": []}}),
        ("response.output_item.added", {"output_index": 0, "item": {**item, "status": "in_progress"}}),
        ("response.output_item.done", {"output_index": 0, "item": item}),
        ("response.completed", {"response": {"id": "resp_mock", "status": "completed", "output": [item],
                                            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}}),
    ]
    return "".join("event: " + name + "\ndata: " + json.dumps({"type": name, **data}) + "\n\n"
                   for name, data in events).encode()


def mock_tool_succeeded(body):
    for item in body["input"]:
        if item["type"] not in {"custom_tool_call_output", "function_call_output"}:
            continue
        output = item.get("output")
        parts = output if isinstance(output, list) else [{"text": output}]
        for part in parts:
            try:
                result = json.loads(part.get("text", ""))
            except (TypeError, ValueError):
                continue
            if (isinstance(result, dict) and result.get("exit_code") == 0
                    and result.get("output", "").strip() == "ISOLATED_TOOL_OK"):
                return True
    return False
