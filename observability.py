"""Best-effort operator telemetry. Never a source of grading or builder feedback."""
from datetime import datetime, timezone
import json
from pathlib import Path
import warnings


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
