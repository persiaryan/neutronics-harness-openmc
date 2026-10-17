"""One allowlisted preloaded procedure; no native skill discovery or candidate execution."""
from pathlib import Path

from builder.context import sha256

ASSISTANCE = 'guided_construction_region_ownership'
PATH = Path(__file__).parent / 'skills/openmc-region-ownership/SKILL.md'
SNAPSHOT = 'region-ownership-skill.md'
HEADER = '\n\nPreloaded domain procedure: openmc-region-ownership-v1.\n'


def material():
    # This is a fixed source resource, never a path selected by the candidate.
    if any(p.is_symlink() for p in (PATH, PATH.parent, PATH.parent.parent)):
        raise ValueError('Region skill must not use symlinks')
    if not PATH.is_file() or PATH.stat().st_nlink != 1 or PATH.stat().st_size > 12000:
        raise ValueError('Region skill must be one bounded regular source file')
    raw = PATH.read_bytes()
    raw.decode('utf-8')
    identity = dict(id='openmc-region-ownership', version='1',
                    delivery='preloaded_prompt', sha256=sha256(raw), bytes=len(raw))
    return raw, identity


def verify(directory, record, assistance):
    """Bind prepared/retained bytes to the declared procedure; A/B/C cannot inherit it."""
    directory = Path(directory)
    path = directory / SNAPSHOT
    if assistance != ASSISTANCE:
        if 'region_ownership_skill' in record or path.exists() or path.is_symlink():
            raise ValueError('Undeclared region skill')
        return
    raw, identity = material()
    if record.get('region_ownership_skill') != identity:
        raise ValueError('Region skill identity changed or missing')
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError('Region skill snapshot missing or linked')
    if path.stat().st_size != len(raw) or path.read_bytes() != raw:
        raise ValueError('Region skill snapshot changed')
