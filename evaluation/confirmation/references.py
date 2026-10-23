"""Read sealed operator references; never substitute historical or public answers."""
import hashlib
import itertools
import json
import math
from pathlib import Path

from evaluator.run import digest
from evaluator.transport_input import read_regular
from evaluator.profiles import PROFILE
from evaluation.benchmark_suite import scoring
from evaluation.benchmark_suite.numerics import compare, difference
from evaluation.scientific.records import require
from evaluation.candidates import receipts
from evaluation.confirmation import cases
from prompts.confirmation import suite

ROOT=Path(__file__).resolve().parents[2]
PROTOCOL=Path(__file__).with_name('protocol.json')
COMPATIBILITY=Path(__file__).with_name('compatibility-indc107-v1.json')
COMPATIBILITY_SHA256='1fafcc50c3a6790299bba5f1bf808294e35d803fe7b865cbb1742a1b59c72a19'


def read(path):
    return json.loads(read_regular(Path(path),limit=32_000_000))


def identity():
    paths=list((ROOT/'evaluation/confirmation').glob('*.py'))+[PROTOCOL,COMPATIBILITY]
    paths += list((ROOT/'evaluation/upstream/indc_usa_107_p1').iterdir())
    paths += [ROOT/p for p in (
        'evaluation/benchmark_suite/suite_cases.py','evaluation/benchmark_suite/suite_checks.py',
        'evaluation/benchmark_suite/scoring.py','evaluation/benchmark_suite/scoring.json',
        'evaluation/candidates/assessment.py','evaluation/candidates/run.py','evaluation/candidates/verify.py',
        'evaluation/scientific/records.py','evaluation/scientific/boundaries.py',
        'evaluation/scientific/worker.py','evaluation/scientific/boundary_worker_v2.py',
        'evaluation/scientific/source_space.py','evaluation/scientific/source_angle.py',
        'evaluator/profiles.py','evaluator/transport.py','evaluator/runtime/transport_worker.py')]
    return {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(set(paths))}


def inventory(folder):
    folder=Path(folder)
    require(folder.is_dir() and not folder.is_symlink(),'Reference folder must be ordinary')
    result={}
    for p in sorted(folder.rglob('*')):
        require(not p.is_symlink(),'Reference links are forbidden')
        if p.is_dir():continue
        require(p.is_file() and p.stat().st_nlink==1,'Reference artifact must be ordinary')
        name=p.relative_to(folder).as_posix()
        if name in ('manifest.json','seal.sha256'):continue
        require(p.stat().st_size<=32_000_000,'Reference artifact too large')
        with p.open('rb') as stream:
            sha=hashlib.file_digest(stream,'sha256').hexdigest()
        result[name]=dict(bytes=p.stat().st_size,sha256=sha)
    require(len(result)<=1500,'Reference inventory too large')
    return result


def numerical(records):
    protocol=read(PROTOCOL)
    require(len(records)==5,'Five qualification runs required')
    require([r['kind'] for r in records]==['primary']*3+['long_inactive','point_source'],'Qualification run matrix changed')
    primary=[r['keff'] for r in records[:3]]
    mean=dict(mean=sum(k['mean'] for k in primary)/3,
        std_dev=math.sqrt(sum(k['std_dev']**2 for k in primary))/3,uncertainty='one sigma')
    pairs=[difference(a,b) for a,b in itertools.combinations(primary,2)]
    controls=[compare(r['keff'],mean,scoring.RUBRIC['equivalence_margin_pcm'],
                      scoring.RUBRIC['interval_multiplier']) for r in records[3:]]
    checks=dict(primary_mean_precision=mean['std_dev']*1e5<=protocol['maximum_primary_mean_sigma_pcm'],
        primary_pair_consistency=all(abs(r['standardized_difference'])<=protocol['maximum_pair_z'] for r in pairs),
        precision=all(r['keff']['std_dev']*1e5<=scoring.RUBRIC['maximum_candidate_std_dev_pcm'] for r in records),
        entropy=all(r['entropy_drift'] is not None and math.isfinite(r['entropy_drift'])
                    and abs(r['entropy_drift'])<=scoring.RUBRIC['entropy_active_half_drift_screen_bits'] for r in records),
        controls_equivalent=all(r['status']=='agreement' for r in controls))
    return dict(primary_mean=mean,pairs=pairs,controls=controls,checks=checks,
                passed=all(checks.values()))


def seal(folder, value):
    folder=Path(folder)
    value=dict(value,format='confirmation-private-reference-v1',case_version=cases.SPECS[value['case']]['version'],
        task_sha256=cases.SPECS[value['case']]['source_sha256'],suite_manifest_sha256=suite()[1],
        evaluator_identity=identity(),rubric=scoring.identity(),protocol_sha256=digest(PROTOCOL.read_bytes()),
        grading_enabled=False,scientific_review='pending_owner_review',files=inventory(folder))
    raw=(json.dumps(value,indent=2,sort_keys=True)+'\n').encode()
    (folder/'manifest.json').write_bytes(raw)
    (folder/'seal.sha256').write_text(digest(raw)+'\n')
    return value



def compatibility():
    raw=read_regular(COMPATIBILITY)
    require(digest(raw)==COMPATIBILITY_SHA256,'Compatibility proof changed')
    return json.loads(raw)


def identity_matches(case, recorded):
    actual=identity()
    if recorded==actual:
        return True
    proof=compatibility()
    if case not in proof['retained_contracts'] or recorded not in proof['previous_identities']:
        return False
    from evaluation.confirmation.indc107 import physical_contract
    if physical_contract(case)!=proof['retained_contracts'][case]:
        return False
    baseline=proof['baseline_identity']
    added=proof['added_files']
    if set(actual)!=set(baseline)|set(added)|{str(COMPATIBILITY.relative_to(ROOT))}:
        return False
    if actual['evaluation/confirmation/cases.py']!=proof['current_cases_sha256']:
        return False
    changed={'evaluation/confirmation/cases.py','evaluation/confirmation/references.py'}
    return (all(actual[path]==sha for path,sha in baseline.items() if path not in changed)
            and all(actual[path]==sha for path,sha in added.items()))


def suite_matches(case, value):
    if value['suite_manifest_sha256']==suite()[1]:
        return True
    proof=compatibility()
    return (case in proof['retained_contracts']
            and value['suite_manifest_sha256']==proof['previous_suite_manifest_sha256']
            and identity_matches(case,value['evaluator_identity']))


def target(case, package, runtime):
    require(runtime is None,'Confirmation v1 uses the pinned private execution profile')
    require(case in cases.SPECS and package is not None,'Explicit confirmation reference required')
    folder=Path(package)
    value=read(folder/'manifest.json');raw=read_regular(folder/'manifest.json')
    require(read_regular(folder/'seal.sha256').decode().strip()==digest(raw),'Reference seal changed')
    require(value['format']=='confirmation-private-reference-v1' and value['case']==case
            and value['technical_status']=='technically_qualified','Reference is not technically qualified')
    require(value['files']==inventory(folder),'Reference evidence inventory changed')
    require(value['task_sha256']==cases.SPECS[case]['source_sha256']
            and value['case_version']==cases.SPECS[case]['version']
            and suite_matches(case,value),'Reference task binding changed')
    require(identity_matches(case,value['evaluator_identity']) and value['rubric']==scoring.identity()
            and value['protocol_sha256']==digest(PROTOCOL.read_bytes()),'Reference implementation/criteria changed')
    require(value['grading_enabled'] is False and value['scientific_review']=='pending_owner_review',
            'Unexpected reference scientific approval')
    result=numerical(value['records'])
    require(result==value['numerical'] and result['passed'],'Reference numerical qualification failed')
    return dict(index=dict(status='verified',manifest_sha256=digest(raw),cases=1),
        reference=dict(kind=value['format'],path=str(folder.resolve()),manifest_sha256=digest(raw),
                       primary_mean=result['primary_mean'],scientific_review='pending_owner_review'),
        protocol={k:PROFILE[k] for k in ('export_image','transport_image')},
        runtime=value['native_identity'],data=value['data'])
