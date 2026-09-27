"""Record actual provider request context and tool declarations."""
import hashlib
import json

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

def tool_declarations(body):
    # Only the session-generated additional_tools ID is nonsemantic.
    return dict(tools=body.get('tools', []), additional_tools=[
        {k:v for k,v in item.items() if k!='id'} for item in body.get('input', [])
        if item.get('type')=='additional_tools'])

def request_setup(body):
    """Effective adapter setup, excluding task text and session-generated IDs."""
    inventory = request_inventory(body)
    return dict(request_configuration={k: body.get(k) for k in (
        'tool_choice', 'parallel_tool_calls', 'reasoning', 'store', 'stream', 'include', 'text')},
        generic_tools_sha256=sha256(json.dumps(tool_declarations(body), sort_keys=True).encode()),
        instruction_messages=inventory['instruction_messages'],
        top_level_instructions_sha256=inventory['top_level_instructions_sha256'])

def request_inventory(body):
    """Inspect both legacy top-level tools and newer input additional_tools.

    An empty body['tools'] does NOT establish a tool-free request. Retain full
    request JSON too: code-mode descriptions can declare further nested tools.
    """
    if not isinstance(body, dict) or not isinstance(body.get("input", []), list):
        raise ValueError("Unexpected request shape")
    tools = []

    def visit(nodes, path):
        if not isinstance(nodes, list):
            raise ValueError(f"Unexpected tool list at {path}")
        for index, node in enumerate(nodes):
            location = f"{path}[{index}]"
            if not isinstance(node, dict):
                tools.append({"path": location, "type": "unknown", "name": "unknown"})
                continue
            kind = node.get("type", "unknown")
            tools.append({"path": location, "type": kind, "name": node.get("name", kind)})
            visit(node.get("tools", []), location + ".tools")

    visit(body.get("tools", []), "tools")
    for index, item in enumerate(body.get("input", [])):
        if not isinstance(item, dict):
            raise ValueError("Unexpected input item")
        if item.get("type") == "additional_tools":
            visit(item.get("tools", []), f"input[{index}].tools")
    texts = [part.get("text", "") for item in body.get("input", [])
             for part in item.get("content", []) if isinstance(part, dict)]
    return {
        "advertised_tools": tools,
        "skills_catalog_present": any("<skills_instructions>" in text for text in texts),
        "memory_block_present": any("## Memory" in text or "MEMORY_SUMMARY" in text for text in texts),
        "top_level_instructions_sha256": sha256(body.get("instructions", "").encode()),
        "top_level_instructions_bytes": len(body.get("instructions", "").encode()),
        "instruction_messages": [
            {"role": item["role"], "bytes": len(part.get("text", "").encode()),
             "sha256": sha256(part.get("text", "").encode()),
             "first_line": part.get("text", "").split("\n")[0]}
            for item in body.get("input", []) if item.get("role") in {"system", "developer"}
            for part in item.get("content", []) if isinstance(part, dict)],
        "input_types": [item.get("type") for item in body.get("input", [])],
        "user_texts": [part.get("text", "") for item in body.get("input", [])
                       if item.get("role") == "user" for part in item.get("content", [])],
    }
