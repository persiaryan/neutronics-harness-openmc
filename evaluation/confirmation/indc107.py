"""Pinned public source provenance; physical expectations remain literal in cases.py."""
import hashlib
import json
from pathlib import Path
from evaluator.transport_input import read_regular
from evaluation.scientific.records import require

UPSTREAM=Path(__file__).resolve().parents[1]/'upstream/indc_usa_107_p1'
COMMIT='ba41bee54320ada0b4ac39a0dd2ca3c1d090a450'
LOCK_SHA256='e124de381276d029e7b43c1d2590e572f92341a7d13d804ee41bf90014d951b7'


def verify_source(folder=UPSTREAM):
    folder=Path(folder)
    raw=read_regular(folder/'manifest.json')
    require(hashlib.sha256(raw).hexdigest()==LOCK_SHA256,'INDC107 source lock changed')
    value=json.loads(raw)
    require(value['commit']==COMMIT and value['repository']=='https://github.com/mit-crpg/benchmarks',
            'INDC107 source revision changed')
    require(set(value['files'])=={'geometry.xml','materials.xml','settings.xml','tallies.xml','LICENSE','upstream-readme.rst'},
            'INDC107 upstream inventory changed')
    for name,record in value['files'].items():
        data=read_regular(folder/name)
        require(len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256'],
                'INDC107 upstream file changed: '+name)
    return value


def physical_contract(case):
    """Fingerprint the complete finite physical contract, without reference code."""
    from evaluation.confirmation import cases
    points,groups=cases.probes(case)
    value=dict(spec=cases.SPECS[case],materials=cases.materials(case),points=points,groups=groups,
        expected=[cases.expected(case,p) for p in points],
        temperatures=[cases.temperature(case,p) for p in points],boundaries=cases.requirements(case))
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
