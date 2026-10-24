"""Fixed native end-to-end development matrix; no evaluated agent or campaign.

Four operator controls exercise compact geometry, equivalent cell restrictions,
a known sampling defect, and an unsupported extra source constraint. The legacy
comparison reads the same final XML/transport, with a separately executed v2
observer. It is not a second independent transport or an efficacy experiment.
"""
import argparse
import json
from pathlib import Path

from evaluator.profiles import PROFILE, REPRESENTATION_PROTOCOL
from evaluator.run import digest, write_json
from evaluator.transport_input import accepted_export, read_regular
from evaluation.candidates import assessment, boundary_assessment, representation, run, verify
from evaluation.benchmark_suite import scoring, suite_checks
from evaluation.benchmark_suite.suite_cases import probes
from evaluation.confirmation import references
from evaluation.scientific import boundaries
from evaluation.scientific.inspection import WORKER, admit
from evaluation.scientific.records import inspection_record, require


def replace_once(source, old, new):
    require(source.count(old)==1,'Control fixture marker missing or ambiguous')
    return source.replace(old,new)


def controls(mapping):
    pin='indc107_reflective_pin'; wrapper='wrapped_eight_pin_channel'
    p=read_regular(Path(mapping[pin])/'reference.py').decode()
    w=read_regular(Path(mapping[wrapper])/'reference.py').decode()
    start='    # Equivalent explicit water partition:'
    end='    # Clip every region'
    require(w.count(start)==1 and w.count(end)==1,'Wrapper partition markers missing')
    a=w.index(start); b=w.index(end)
    compact=w[:a]+'    add(domain&~openmc.Union(occupied),water)\n'+w[b:]
    return [
        dict(id='compact-wrapper',case=wrapper,source=compact,expected='conforming_within_protocol'),
        dict(id='cell-selected-source',case=pin,
             source=replace_once(p,"constraints={'fissionable':True}","constraints={'domains':[cells[0]]}"),
             expected='conforming_within_protocol'),
        dict(id='wrong-particle-count',case=pin,
             source=replace_once(p,'settings.particles = 10000','settings.particles = 5000'),expected='nonconforming'),
        dict(id='unsupported-energy-restriction',case=pin,
             source=replace_once(p,"constraints={'fissionable':True}",
                                 "constraints={'fissionable':True,'energy_bounds':[0.,1.e9]}"),expected='indeterminate')]


def plan(mapping):
    return dict(format='representation-development-plan-v1',provider_calls=0,campaign_candidates=0,
        original_outcomes_reassessed=False,maximum_native_transport_calls=4,automatic_retries=0,
        transport_seconds_per_case=1800,evaluator_protocol=REPRESENTATION_PROTOCOL,
        semantics=representation.identity(),controller_sha256=digest(Path(__file__).read_bytes()),
        rows=[{k:v for k,v in row.items() if k!='source'}|dict(source_sha256=digest(row['source'].encode()),
             reference_manifest_sha256=digest(read_regular(Path(mapping[row['case']])/'manifest.json'))) for row in controls(mapping)],
        interpretation='Fixed development controls, conditional on protocol coverage; no unseen confirmation, power or efficacy claim')


def row_result(control,report,review,legacy):
    actual=report['conclusion']['conformance']
    verified=review['evidence_status']=='coherent'
    passed=verified and report['status']=='assessed' and actual==control['expected']
    if control['expected']=='conforming_within_protocol':passed=passed and report['diagnostic_score']['strict_correct']
    if control['expected']=='nonconforming':
        passed=passed and 'physics_settings.sampling' in report['conclusion']['known_mismatches']
    if control['expected']=='indeterminate':
        passed=passed and report['diagnostic_score']['score'] is None and 'physics_settings.source' in report['conclusion']['unassessed_checks']
    return dict(id=control['id'],case=control['case'],expected=control['expected'],actual=actual,passed=passed,
        evidence_status=review['evidence_status'],score=report['diagnostic_score']['score'],
        strict_correct=report['diagnostic_score']['strict_correct'],legacy=legacy,
        known_mismatches=report['conclusion']['known_mismatches'],unassessed_checks=report['conclusion']['unassessed_checks'])


def legacy_comparison(control,folder,*,execute=False):
    report=references.read(folder/'assessment/report.json'); xml,_=accepted_export(folder/'assessment/export')
    output=folder/'legacy-boundaries'
    if execute:boundaries.observe(xml,output,version=boundaries.VERSION,image=PROFILE['export_image'],wall_seconds=120)
    obs=inspection_record(control['case'],folder/'assessment/export-inspection',xml,WORKER.read_bytes(),image=PROFILE['export_image'])
    boundary=boundary_assessment.evaluate(boundaries.record(output,xml,version=boundaries.VERSION,image=PROFILE['export_image']),
                                         boundaries.requirements(control['case']),obs)
    fidelity=suite_checks.assess(control['case'],admit(xml),obs,report['assignment']['sampling'],boundary_result=boundary)
    checks=assessment.fidelity_checks(control['case'],fidelity,obs)
    # Transport and numeric evidence are identical to the newly verified v6 run.
    for group in checks:
        if group not in ('materials','geometry','physics_settings'):checks[group]=report['checks'][group]
    score=scoring.score(report['gates'],checks)
    return dict(score=score['score'],strict_correct=score['strict_correct'],checks=checks,
                transport_evidence='same_verified_prospective_execution',boundary_cause=boundary.get('status'))


def execute(mapping,output,index):
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    frozen=plan(mapping);write_json(output/'plan.json',frozen);rows=[]
    for control in controls(mapping):
        require(references.read(output/'plan.json')==plan(mapping),'Development plan or fixture changed')
        folder=output/control['id'];folder.mkdir();candidate=folder/'candidate.py';candidate.write_text(control['source'])
        report=run.evaluate(control['case'],folder/'assessment',index=index,candidate=candidate,
                            reference=Path(mapping[control['case']]),evaluator_protocol=REPRESENTATION_PROTOCOL)
        review=verify.review_assessment(folder/'assessment',index,reference=Path(mapping[control['case']]))
        write_json(folder/'review.json',review)
        require(review['evidence_status']=='coherent' and report['status']=='assessed',
                'Native integration incident; retain evidence and stop without retry')
        legacy=legacy_comparison(control,folder,execute=True)
        write_json(folder/'legacy-comparison.json',legacy)
        row=row_result(control,report,review,legacy);rows.append(row)
        write_json(output/'report.json',dict(format='representation-development-results-v1',plan_sha256=digest(read_regular(output/'plan.json')),
            rows=rows,status='passed' if len(rows)==4 and all(r['passed'] for r in rows) else 'incomplete_or_failed',
            provider_calls=0,original_outcomes_reassessed=False))
        print(json.dumps(row),flush=True)
    return rows


def reconstruct(mapping,output,index):
    output=Path(output);require(references.read(output/'plan.json')==plan(mapping),'Development plan changed');rows=[]
    for control in controls(mapping):
        folder=output/control['id']
        require(read_regular(folder/'candidate.py')==control['source'].encode(),'Development candidate changed')
        review=verify.review_assessment(folder/'assessment',index,reference=Path(mapping[control['case']]))
        require(review==references.read(folder/'review.json'),'Development review changed')
        legacy=legacy_comparison(control,folder)
        require(legacy==references.read(folder/'legacy-comparison.json'),'Legacy comparison changed')
        rows.append(row_result(control,references.read(folder/'assessment/report.json'),review,legacy))
    report=references.read(output/'report.json')
    require(report==dict(format='representation-development-results-v1',plan_sha256=digest(read_regular(output/'plan.json')),
        rows=rows,status='passed' if all(r['passed'] for r in rows) else 'incomplete_or_failed',
        provider_calls=0,original_outcomes_reassessed=False),'Development summary changed')
    return dict(status='verified',requirements_met=all(r['passed'] for r in rows),controls=len(rows),report_sha256=digest(read_regular(output/'report.json')))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('references','output','data-index'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--verify',action='store_true');a=p.parse_args()
    mapping=references.read(a.references)
    result=reconstruct(mapping,a.output,a.data_index) if a.verify else execute(mapping,a.output,a.data_index)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
