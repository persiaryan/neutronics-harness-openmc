"""Reconstruct private reference qualification from retained native evidence."""
import argparse
from pathlib import Path

from builder.context import write_json
from evaluation.confirmation import cases, references
from evaluation.candidates import assessment, boundary_assessment, receipts
from evaluation.candidates.phase_evidence import export_outcome
from evaluation.benchmark_suite.suite_checks import assess
from evaluation.scientific import boundaries
from evaluation.scientific.inspection import WORKER, admit
from evaluation.scientific.records import inspection_record, require
from evaluator.run import digest
from evaluator.profiles import PROFILE
from evaluator.transport_input import accepted_export
from prompts.confirmation import TASKS


def review(case, package, index):
    package=Path(package)
    goal=references.target(case,package,None)
    value=references.read(package/'manifest.json')
    review_runs(case,package,index,goal,value)
    return dict(format='confirmation-reference-evidence-review-v1',case=case,evidence_status='coherent',
                reference_manifest_sha256=goal['index']['manifest_sha256'],reconstructed_runs=5,
                evaluator_identity=references.identity(),generation_evaluator_identity=value['evaluator_identity'],
                generation_identity_compatibility_applied=value['evaluator_identity']!=references.identity(),
                scientific_review='pending_owner_review')


def review_runs(case,package,index,goal,value):
    """Reconstruct physical/numerical evidence; caller handles package admission."""
    package=Path(package)
    report=references.read(package/'qualification.json')
    require(value['records']==report['records'] and value['numerical']==report['numerical']
            and value['technical_status']==report['technical_status'],'Reference summary binding changed')
    require(digest((package/'reference.py').read_bytes())==value['source_sha256'],'Base reference source changed')
    protocol=references.read(references.PROTOCOL)
    seeds=protocol['primary_seeds']+[protocol['control_seed'],protocol['source_seed']]
    require([r['seed'] for r in value['records']]==seeds,'Reference seed matrix changed')
    for n,row in enumerate(value['records']):
        relative=Path(row['folder'])
        require(not relative.is_absolute() and '..' not in relative.parts,'Reference run outside package')
        folder=package/relative
        source_hash=digest((folder/'reference.py').read_bytes())
        require(source_hash==row['source_sha256'],'Reference variant source changed')
        require(export_outcome(folder/'export',PROFILE['export_image'],index,source_hash)==dict(cause=None,reason=None),
                'Reference export evidence failed')
        xml,_=accepted_export(folder/'export')
        require(digest(xml)==row['xml_sha256'],'Reference XML changed')
        sampling=dict(protocol['sampling'],seed=seeds[n])
        if n==3:sampling.update(protocol['long_inactive'])
        if n==4:sampling['source']='point'
        require(row['sampling']==sampling,'Reference sampling matrix changed')
        obs=inspection_record(case,folder/'inspection',xml,WORKER.read_bytes(),image=PROFILE['export_image'])
        require(obs['status']=='inspected','Reference inspection incomplete')
        boundary=boundary_assessment.evaluate(boundaries.record(folder/'boundaries',xml,image=PROFILE['export_image']),
                                              boundaries.requirements(case),obs)
        fidelity=assess(case,admit(xml),obs,sampling,boundary_result=boundary)
        require(fidelity==references.read(folder/'fidelity.json'),'Reference physical observations changed')
        checks=assessment.fidelity_checks(case,fidelity,obs)
        require(all(v is True for g in ('geometry','materials','physics_settings') for v in checks[g].values()),
                'Reference physical conformity not established')
        actual=receipts.transport_record(folder,source_hash,PROFILE['transport_image'],index)
        drift=actual['convergence']['statistics'].get('entropy_bits',{}).get('second_minus_first')
        require(actual['keff']==row['keff'] and drift==row['entropy_drift']
                and actual['sampling']=={k:v for k,v in sampling.items() if k!='source'}
                and actual['data']==goal['data'] and actual['runtime']==goal['runtime'],
                'Reference numerical/runtime/data summary contradicts retained execution')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=TASKS,required=True)
    for name in ('reference','data-index','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    require(not a.output.exists(),'Use a fresh reference-review output')
    value=review(a.case,a.reference,a.data_index.resolve(strict=True))
    write_json(a.output,value)
    print(value['evidence_status'])


if __name__=='__main__':
    main()
