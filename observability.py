"""Best-effort operator telemetry. Never a source of grading or builder feedback."""
from datetime import datetime, timezone
import json
from pathlib import Path
import warnings
import hashlib


def now():
    return datetime.now(timezone.utc).isoformat()


def record(directory, phase, state, **details):
    """Append complete records; failures do not change experimental outcomes."""
    try:
        line = json.dumps(dict(time=now(), phase=phase, state=state, **details),
                          ensure_ascii=False, allow_nan=False) + '\n'
        with (Path(directory) / 'progress.jsonl').open('a') as stream:
            stream.write(line)
    except (OSError, ValueError, TypeError) as exc:
        # Diagnostics contain no candidate content or credentials.
        try:
            warnings.warn('Operator telemetry unavailable: ' + type(exc).__name__, RuntimeWarning)
        except Exception:
            pass


def tool_observation(directory, tool_id, version, *, started=None, elapsed_seconds=None):
    """Host-only envelope; request/result/feedback bytes and delivery evidence stay original."""
    try:
        from observation_contracts import identifier
        identifier(tool_id); identifier(version)
        directory=Path(directory)
        artifacts={}
        for name in ('request.json','response.json','feedback.json'):
            path=directory/name
            if path.is_file() and not path.is_symlink():
                artifacts[name]=dict(path=name,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        value=dict(format='tool-observation-v1',tool_id=tool_id,tool_version=version,call_id=directory.name,
                   started=started,finished=now(),elapsed_seconds=elapsed_seconds,artifacts=artifacts,
                   feedback_delivery='not_established_by_completion')
        (directory/'observation.json').write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    except (OSError,ValueError,TypeError) as exc:
        try: warnings.warn('Operator tool observation unavailable: '+type(exc).__name__,RuntimeWarning)
        except Exception: pass
