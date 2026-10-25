"""Trusted native sampling/crossing controls; receives only synthetic XML."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import openmc


def main(payload):
    if openmc.__version__!='0.15.3': raise RuntimeError('Pinned OpenMC required')
    os.chdir('/tmp')
    # This pinned transport image installs the Python bindings separately from
    # /opt/openmc/lib. Stage byte-identical bindings in tmpfs with the expected
    # library symlink; no upstream source or native library is modified.
    original=Path(openmc.__file__).parent/'lib'
    staged=Path('/tmp/native-python/openmc/lib')
    shutil.copytree(original,staged,ignore=shutil.ignore_patterns('__pycache__'))
    (staged/'libopenmc.so').symlink_to('/opt/openmc/lib/libopenmc.so')
    openmc.__path__.insert(0,str(staged.parent))
    from openmc import lib
    Path('model.xml').write_text(payload['xml'])
    result=dict(openmc_version=openmc.__version__,mode=payload['mode'],
                model_xml_sha256=hashlib.sha256(payload['xml'].encode()).hexdigest(),
                python_binding_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(original.glob('*.py'))},
                native_files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                              [Path('/opt/openmc/bin/openmc'),Path('/opt/openmc/lib/libopenmc.so')]})
    with lib.run_in_memory(output=False):
        if payload['mode']=='sample':
            if payload['samples']!=4096 or payload['seed']!=41: raise ValueError('Fixed control budget required')
            sites=lib.sample_external_source(payload['samples'],prn_seed=payload['seed'])
            result.update(status='sampled',seed=payload['seed'],positions=[list(p.r) for p in sites])
        elif payload['mode']=='crossing':
            lib.run()
            # Eigenvalue estimators are undefined in this void fixed-source
            # control. Only the leakage estimator is a requested observable.
            leakage=lib.global_tallies()[3]
            result.update(status='transport_completed',leakage=dict(mean=float(leakage[0]),std_dev=float(leakage[1])))
        else:
            raise ValueError('Unknown control mode')
    return result


if __name__=='__main__':
    print(json.dumps(main(json.loads(sys.stdin.buffer.read(4_000_001))),separators=(',',':'),allow_nan=False))
