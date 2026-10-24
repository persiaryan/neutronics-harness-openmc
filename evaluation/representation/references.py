"""Explicit requalification of unchanged, retained reference calculations.

The predecessor seal is provenance, never an exemption from reconstruction.
Five original native runs are verified, then new XML-only observations qualify
the prospective representation semantics. No neutron calculation is rerun here.
"""
import argparse
import json
from pathlib import Path
import shutil

from evaluator.profiles import PROFILE
from evaluator.run import digest, write_json
from evaluator.transport_input import accepted_export, read_regular
from evaluation.benchmark_suite import scoring
from evaluation.benchmark_suite.suite_cases import probes
from evaluation.candidates import representation, run
from evaluation.candidates import boundary_assessment
from evaluation.confirmation import cases, qualify, references
from evaluation.scientific import boundaries, source_domains
from evaluation.scientific.inspection import WORKER, admit
from evaluation.scientific.records import inspection_record, require
from experiments import confirmation_reference_review
from prompts.confirmation import suite


def predecessor(package, case):
    package=Path(package)
    raw=read_regular(package/'manifest.json'); value=json.loads(raw)
    require(read_regular(package/'seal.sha256').decode().strip()==digest(raw), 'Predecessor seal changed')
    require(value['format']=='confirmation-private-reference-v1' and value['case']==case and
            value['technical_status']=='technically_qualified', 'Predecessor is not a qualified reference')
    require(value['files']==references.inventory(package), 'Predecessor inventory changed')
    require(value['task_sha256']==cases.SPECS[case]['source_sha256'] and
            value['case_version']==cases.SPECS[case]['version'] and
            value['rubric']==scoring.identity() and
            value['protocol_sha256']==digest(references.PROTOCOL.read_bytes()),
            'Retained reference physical task or numerical criteria changed')
    require(value['grading_enabled'] is False and value['scientific_review']=='pending_owner_review',
            'Predecessor approval boundary changed')
    require(value['numerical']==references.numerical(value['records']) and value['numerical']['passed'],
            'Predecessor numerical qualification failed')
    return value


def reconstruct(case, package, index, value):
    """Use the existing full five-run verifier after explicit identity rebinding.

    Its target admission is handled separately; this helper supplies no identity
    compatibility exception. Exact variant generation is checked additionally.
    """
    source=read_regular(package/'reference.py')
    for row in value['records']:
        relative=Path(row['folder'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'Run outside reference package')
        folder=package/relative
        require(read_regular(folder/'reference.py')==qualify.variant(source,folder,row['kind'],row['seed']),
                'Retained reference variant differs from the fixed qualification plan')
    goal=dict(data=value['data'],runtime=value['native_identity'],index=dict(manifest_sha256=digest(read_regular(package/'manifest.json'))))
    confirmation_reference_review.review_runs(case,package,index,goal,value)
    # Hash the currently mounted data and inspect pinned runtime identities.
    run.preflight(index,dict(data=value['data'],runtime=value['native_identity'],
                            protocol={k:PROFILE[k] for k in ('export_image','transport_image')}))


def observe(case, package):
    rows=[]
    value=references.read(package/'qualification.json')
    for row in value['records']:
        folder=package/row['folder']; xml,_=accepted_export(folder/'export')
        output=package/'representation'/row['folder']
        boundaries.observe(xml,output/'boundaries',image=PROFILE['export_image'],version=boundaries.NEXT_VERSION)
        source_domains.observe(xml,probes(case)[0],output/'source-domains',image=PROFILE['export_image'])
        rows.append(compare(case,package,row))
        print(json.dumps(dict(event='reference_observed',case=case,kind=row['kind'],seed=row['seed'])),flush=True)
    return rows


def compare(case, package, row):
    folder=package/row['folder']; xml,_=accepted_export(folder/'export')
    output=package/'representation'/row['folder']
    obs=inspection_record(case,folder/'inspection',xml,WORKER.read_bytes(),image=PROFILE['export_image'])
    boundary=boundary_assessment.evaluate(boundaries.record(output/'boundaries',xml,
        image=PROFILE['export_image'],version=boundaries.NEXT_VERSION),boundaries.requirements(case),obs)
    source=source_domains.record(output/'source-domains',xml,probes(case)[0],image=PROFILE['export_image'])
    if row['kind']=='point_source':
        # This intentional initialization control has a different required law.
        # Its point source is reconstructed by the existing qualification verifier;
        # prospective uniform-support equivalence is deliberately inapplicable.
        require(boundary['score_check'] is True,'Point-control boundaries unresolved')
        return dict(folder=row['folder'],boundary=True,source_support='point_control_checked_by_reference_verifier')
    fidelity=representation.assess(case,admit(xml),obs,row['sampling'],boundary_result=boundary,source_observation=source)
    checks=representation.fidelity_checks(case,fidelity,obs)
    require(all(v is True for group in ('materials','geometry','physics_settings') for v in checks[group].values()),
            'Prospective reference fidelity unresolved or nonconforming')
    return dict(folder=row['folder'],boundary=True,source_support=fidelity['settings']['source_support'],checks=checks)


def requalify(case, original, output, index):
    original=Path(original); output=Path(output)
    require(not output.exists(),'Use a fresh reference package; no automatic retries')
    value=predecessor(original,case)
    reconstruct(case,original,index,value)
    shutil.copytree(original,output)
    prior=output/'predecessor';prior.mkdir()
    for name in ('manifest.json','seal.sha256','qualification.json'):
        shutil.copyfile(output/name,prior/name)
    (output/'manifest.json').unlink();(output/'seal.sha256').unlink()
    report=dict(value); report.pop('files');report.pop('evaluator_identity')
    report.update(technical_status='requalifying',requalification=dict(
        format='retained-reference-requalification-v1',predecessor_manifest_sha256=digest(read_regular(prior/'manifest.json')),
        numerical_execution='retained_original_five_runs',new_neutron_transport_calls=0,
        current_suite_manifest_sha256=suite()[1],semantics=representation.identity()))
    write_json(output/'qualification.json',report)
    rows=observe(case,output)
    report['requalification']['rows']=rows
    report['technical_status']='technically_qualified'
    write_json(output/'qualification.json',report)
    references.seal(output,report)
    return verify(case,output,index)


def verify(case, package, index):
    package=Path(package); value=references.read(package/'manifest.json')
    review=confirmation_reference_review.review(case,package,index)
    prior=package/'predecessor';raw=read_regular(prior/'manifest.json'); old=json.loads(raw)
    require(digest(raw)==read_regular(prior/'seal.sha256').decode().strip(),'Retained predecessor seal changed')
    require(old['case']==case and old['records']==value['records'] and old['source_sha256']==value['source_sha256'] and
            old['data']==value['data'] and old['native_identity']==value['native_identity'] and
            old['numerical']==value['numerical'],'Requalification changed retained physical/numerical evidence')
    for name,record in old['files'].items():
        path=prior/name if name=='qualification.json' else package/name
        contents=read_regular(path,limit=32_000_000)
        require(record==dict(bytes=len(contents),sha256=digest(contents)), 'Copied predecessor artifact changed: '+name)
    meta=value['requalification']
    require(meta==dict(format='retained-reference-requalification-v1',predecessor_manifest_sha256=digest(raw),
        numerical_execution='retained_original_five_runs',new_neutron_transport_calls=0,
        current_suite_manifest_sha256=suite()[1],semantics=representation.identity(),
        rows=[compare(case,package,row) for row in value['records']]),'Prospective reference observations changed')
    return dict(review,format='representation-reference-review-v1',requalification=meta,
                new_neutron_transport_calls=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--references',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--data-index',type=Path,required=True)
    p.add_argument('--verify',action='store_true')
    a=p.parse_args(); mapping=references.read(a.references); rows=[]; selected={}
    require(set(mapping)==set(cases.SPECS),'Exactly the twelve current task references are required')
    if not a.verify:a.output.mkdir(parents=True,exist_ok=False)
    for case,path in mapping.items():
        package=Path(path) if a.verify else a.output/case
        review=verify(case,package,a.data_index) if a.verify else requalify(case,path,package,a.data_index)
        if not a.verify:write_json(a.output/(case+'-review.json'),review)
        rows.append(dict(case=case,evidence_status=review['evidence_status'],reconstructed_runs=5,
                         reference_manifest_sha256=review['reference_manifest_sha256']))
        selected[case]=str(package.resolve())
        if not a.verify:
            write_json(a.output/'references.json',selected)
            write_json(a.output/'summary.json',dict(format='representation-reference-summary-v1',rows=rows,
                new_neutron_transport_calls=0,retained_runs_reconstructed=5*len(rows),provider_calls=0))
        print(json.dumps(dict(event='reference_requalified' if not a.verify else 'reference_verified',case=case)),flush=True)
    return rows


if __name__=='__main__':main()
