"""One allowlisted procedure: preloaded D or native selective discovery E."""
import base64
import json
from pathlib import Path

from builder.context import sha256

ASSISTANCE = 'guided_construction_region_ownership'
SELECTIVE = 'guided_construction_region_skill_selective'
ENABLED = (ASSISTANCE, SELECTIVE)
CONTAINER_PATH = '/work/.agents/skills/openmc-region-ownership/SKILL.md'
CATALOG_SNAPSHOT = 'region-ownership-catalog.txt'
PATH = Path(__file__).parent / 'skills/openmc-region-ownership/SKILL.md'
SNAPSHOT = 'region-ownership-skill.md'
HEADER = '\n\nPreloaded domain procedure: openmc-region-ownership-v1.\n'


def material(assistance=ASSISTANCE):
    if assistance not in ENABLED:
        raise ValueError("Unknown region skill delivery")
    # This is a fixed source resource, never a path selected by the candidate.
    if any(p.is_symlink() for p in (PATH, PATH.parent, PATH.parent.parent)):
        raise ValueError('Region skill must not use symlinks')
    if not PATH.is_file() or PATH.stat().st_nlink != 1 or PATH.stat().st_size > 12000:
        raise ValueError('Region skill must be one bounded regular source file')
    raw = PATH.read_bytes()
    raw.decode('utf-8')
    identity = dict(id='openmc-region-ownership', version='1',
                    delivery='preloaded_prompt', sha256=sha256(raw), bytes=len(raw))
    if assistance == SELECTIVE:
        identity.update(delivery='native_skill_catalog', path=CONTAINER_PATH,
                        catalog_sha256=sha256(catalog(raw).encode()),
                        staging_sha256=sha256(STAGE.encode()))
    return raw, identity


def verify(directory, record, assistance):
    """Bind prepared/retained bytes to the declared procedure; A/B/C cannot inherit it."""
    directory = Path(directory)
    path = directory / SNAPSHOT
    if assistance not in ENABLED:
        if ('region_ownership_skill' in record or path.exists() or path.is_symlink()
                or (directory/CATALOG_SNAPSHOT).exists() or (directory/CATALOG_SNAPSHOT).is_symlink()):
            raise ValueError('Undeclared region skill')
        return
    raw, identity = material(assistance)
    if record.get('region_ownership_skill') != identity:
        raise ValueError('Region skill identity changed or missing')
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError('Region skill snapshot missing or linked')
    if path.stat().st_size != len(raw) or path.read_bytes() != raw:
        raise ValueError('Region skill snapshot changed')

    snapshot = directory / CATALOG_SNAPSHOT
    if assistance == SELECTIVE:
        if (snapshot.is_symlink() or not snapshot.is_file() or snapshot.stat().st_nlink != 1
                or snapshot.stat().st_size != len(catalog(raw).encode())
                or snapshot.read_bytes() != catalog(raw).encode()):
            raise ValueError('Region skill catalog snapshot changed or missing')
    elif snapshot.exists() or snapshot.is_symlink():
        raise ValueError('Undeclared region skill catalog')


def catalog(raw):
    """Exact native catalog format qualified against Codex CLI 0.153.4."""
    parts = raw.decode().split('---\n', 2)
    if len(parts) != 3 or parts[0]:
        raise ValueError('Region skill frontmatter missing')
    fields = [line.partition(': ') for line in parts[1].strip().splitlines()]
    if ([f[0] for f in fields] != ['name', 'description']
            or fields[0][2] != 'openmc-region-ownership' or not fields[1][2]):
        raise ValueError('Region skill metadata changed shape')
    return (
        '<skills_instructions>\n## Skills\n'
        'A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. '
        'Below is the list of skills that can be used. Each entry includes a name, description, '
        'and a short path that can be expanded into an absolute path using the skill roots table.\n'
        '### Skill roots\n- `r0` = `/work/.agents/skills`\n### Available skills\n'
        '- openmc-region-ownership: ' + fields[1][2] +
        ' (file: r0/openmc-region-ownership/SKILL.md)\n</skills_instructions>')


# Staged before the unchanged entrypoint creates home/state/workspace. The empty
# .git directory marks /work as the discovery root; it contains no host repository.
# Mode bits discourage accidental edits, but candidate-owned tmpfs is not tamper-proof.
STAGE = """import base64, hashlib, json
from pathlib import Path
import sys
Path('/work/.git').mkdir(mode=0o555)
path = Path('/work/.agents/skills/openmc-region-ownership/SKILL.md')
path.parent.mkdir(parents=True)
raw = base64.b64decode(sys.argv[1], validate=True)
with path.open('xb') as stream:
    stream.write(raw)
path.chmod(0o444)
print(json.dumps(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)))
"""


def staging_receipt(raw):
    return dict(path=CONTAINER_PATH, sha256=sha256(raw), bytes=len(raw))


def stage(docker, container, raw, timeout):
    receipt = json.loads(docker('exec', container, 'python3', '-I', '-B', '-c',
                               STAGE, base64.b64encode(raw).decode(), timeout=timeout))
    if receipt != staging_receipt(raw):
        raise ValueError('Region skill staging receipt changed')
    return receipt


def initial_context(body, prompt, assistance):
    """Keep historical context exclusions; E permits exactly its one native catalog."""
    from builder.context import request_inventory
    inventory = request_inventory(body)
    if (inventory['memory_block_present'] or len(inventory['user_texts']) != 2
            or not inventory['user_texts'][0].startswith('<environment_context>')
            or inventory['user_texts'][-1] != prompt):
        return False
    if assistance != SELECTIVE:
        return not inventory['skills_catalog_present']
    texts = [(item.get('role'), part.get('text', ''))
             for item in body.get('input', []) for part in item.get('content', [])
             if isinstance(part, dict)]
    raw, _ = material(SELECTIVE)
    catalogs = [(role, text) for role, text in texts if '<skills_instructions>' in text]
    # Reject a catalog embedded in other text, extra skills, or a preloaded body.
    return (catalogs == [('developer', catalog(raw))]
            and json.dumps(raw.decode())[1:-1] not in json.dumps(body)
            and raw.decode().split('---\n', 2)[2].strip() not in
                '\n'.join([body.get('instructions', '')] + [t for _, t in texts]))


def reviewed_setups(setups):
    """A/D share a setup; E differs only by the exact catalog instruction part."""
    if set(setups) != {'A', 'D', 'E'} or setups['A'] != setups['D']:
        raise ValueError('Review separate A/D/E setups with identical A and D')
    a, e = setups['A'], setups['E']
    text = catalog(material(SELECTIVE)[0])
    part = dict(role='developer', bytes=len(text.encode()), sha256=sha256(text.encode()),
                first_line='<skills_instructions>')
    messages = list(e.get('instruction_messages', []))
    if messages.count(part) != 1:
        raise ValueError('Reviewed E setup must contain exactly the qualified skill catalog')
    messages.remove(part)
    if dict(e, instruction_messages=messages) != a:
        raise ValueError('Reviewed E setup changes more than the skill catalog')
