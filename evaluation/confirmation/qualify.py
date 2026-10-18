"""Budgeted private reference qualification. No evaluated LLM or provider calls."""
import argparse
import json
from pathlib import Path
import time

from builder.context import write_json
from evaluator import run as exporter, transport
from evaluator.profiles import PROFILE, CONFIRMATION_PROTOCOL
from evaluator.transport_input import accepted_export, transport_profile, read_regular
from evaluation.candidates import assessment, boundary_assessment, receipts
from evaluation.candidates.phase_evidence import export_outcome
from evaluation.candidates.run import clean_resources
from evaluation.scientific import boundaries
from evaluation.scientific.inspection import inspect_xml, WORKER, admit
from evaluation.scientific.records import inspection_record, require, leakage
from evaluation.benchmark_suite.suite_cases import probes
from evaluation.benchmark_suite.suite_checks import assess
from evaluation.confirmation import cases, references
from prompts.confirmation import TASKS


def variant(source, folder, kind, seed):
    text=source.decode()
    require(text.count('    settings.seed = 1\n')==1,'Reference seed marker missing')
    text=text.replace('    settings.seed = 1\n',f'    settings.seed = {seed}\n')
    if kind=='long_inactive':
        text=text.replace('settings.batches = 400','settings.batches = 600')
        text=text.replace('settings.inactive = 100','settings.inactive = 300')
        text=text.replace("settings.statepoint={'batches':[400]}","settings.statepoint={'batches':[600]}")
    if kind=='point_source':
        marker='    mesh=openmc.RegularMesh()'
        require(text.count(marker)==1,'Reference source marker missing')
        point=cases.SPECS[folder.parent.name]['point']
        text=text.replace(marker,
            f"    settings.source=openmc.IndependentSource(space=openmc.stats.Point({point!r}),"
            "angle=openmc.stats.Isotropic(),energy=openmc.stats.Watt(988000.,2.249e-6),"
            "constraints={'fissionable':True})\n"+marker)
    return text.encode()


def inspect(case, folder, source, index, sampling):
    image=PROFILE['export_image'];source_hash=exporter.digest(source)
    result=exporter.evaluate(folder/'reference.py',folder/'export',index=index,image=image)
    require(result['status']=='exported','Reference export failed: '+str(result.get('reason')))
    require(export_outcome(folder/'export',image,index,source_hash)==dict(cause=None,reason=None),
            'Reference export evidence failed')
    xml,_=accepted_export(folder/'export')
    inspect_xml(xml,probes(case)[0],folder/'inspection',wall_seconds=120,image=image)
    obs=inspection_record(case,folder/'inspection',xml,WORKER.read_bytes(),image=image)
    require(obs['status']=='inspected','Reference inspection failed')
    boundaries.observe(xml,folder/'boundaries',image=image)
    boundary=boundary_assessment.evaluate(boundaries.record(folder/'boundaries',xml,image=image),
                                         boundaries.requirements(case),obs)
    fidelity=assess(case,admit(xml),obs,sampling,boundary_result=boundary)
    write_json(folder/'fidelity.json',fidelity)
    checks=assessment.fidelity_checks(case,fidelity,obs)
    require(all(v is True for category in ('materials','geometry','physics_settings')
                for v in checks[category].values()),'Reference physical fidelity failed; inspect fidelity.json')
    return transport_profile(xml,index.name)


def qualify(case, source, output, index):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source=read_regular(Path(source));(output/'reference.py').write_bytes(source)
    protocol=references.read(references.PROTOCOL)
    report=dict(case=case,technical_status='qualifying',records=[],provider_calls=0,
        automatic_retries=0,source_sha256=exporter.digest(source),started=time.time())
    write_json(output/'qualification.json',report)
    specs=[('primary',s) for s in protocol['primary_seeds']]+[
        ('long_inactive',protocol['control_seed']),('point_source',protocol['source_seed'])]
    try:
        clean_resources()
        for number,(kind,seed) in enumerate(specs):
            folder=output/f'run-{number+1}-{kind}';folder.mkdir()
            raw=variant(source,folder,kind,seed)
            (folder/'reference.py').write_bytes(raw)
            sampling=dict(protocol['sampling'],seed=seed)
            if kind=='long_inactive':sampling.update(protocol['long_inactive'])
            if kind=='point_source':sampling['source']='point'
            print(json.dumps(dict(event='reference_started',case=case,kind=kind,seed=seed)),flush=True)
            profile=inspect(case,folder,raw,index,sampling)
            result=transport.transport(folder/'export',folder/'transport',index=index,
                        image=PROFILE['transport_image'],wall_seconds=protocol['maximum_transport_seconds'])
            require(result['status']=='calculated_unreviewed','Reference transport failed: '+str(result.get('reason')))
            record=receipts.transport_record(folder,exporter.digest(raw),PROFILE['transport_image'],index)
            leak=leakage((folder/'transport/openmc-stdout.txt').read_text())
            require(0<=leak['mean']<=1 and (leak['mean']==0 if cases.SPECS[case]['boundary']=='reflective' else leak['mean']>0),
                    'Reference leakage inconsistent with boundaries')
            if not report['records']:
                report.update(data=record['data'],native_identity=record['runtime'])
            require(record['data']==report['data'] and record['runtime']==report['native_identity'],
                    'Reference dependencies changed across seeds')
            drift=record['convergence']['statistics'].get('entropy_bits',{}).get('second_minus_first')
            row=dict(kind=kind,seed=seed,folder=folder.name,keff=record['keff'],entropy_drift=drift,
                     sampling=sampling,xml_sha256=exporter.digest(record['xml']),source_sha256=exporter.digest(raw))
            report['records'].append(row);write_json(output/'qualification.json',report)
            print(json.dumps(dict(event='reference_finished',case=case,kind=kind,keff=record['keff'],entropy_drift=drift)),flush=True)
        report['numerical']=references.numerical(report['records'])
        report['technical_status']='technically_qualified' if report['numerical']['passed'] else 'numerical_qualification_failed'
    except Exception as exc:
        report.update(technical_status='blocked',error_type=type(exc).__name__,reason=str(exc))
    finally:
        clean_resources()
        report['finished']=time.time()
        write_json(output/'qualification.json',report)
    if report['technical_status']=='technically_qualified':
        references.seal(output,report)
        references.target(case,output,None)
    print(json.dumps(dict(event='qualification_finished',case=case,status=report['technical_status'],reason=report.get('reason'))),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--data-index',type=Path,required=True)
    p.add_argument('--cases',nargs='+',choices=TASKS,default=list(TASKS))
    a=p.parse_args()
    require(not a.output.exists(),'Use a fresh qualification directory; no automatic retry')
    a.output.mkdir(parents=True)
    write_json(a.output/'protocol.json',references.read(references.PROTOCOL))
    write_json(a.output/'implementation.json',references.identity())
    rows=[]
    for case in a.cases:
        require(references.read(a.output/'implementation.json')==references.identity(),'Qualification implementation changed')
        rows.append(qualify(case,a.sources/(case+'.py'),a.output/case,a.data_index.resolve(strict=True)))
        write_json(a.output/'summary.json',dict(format='confirmation-qualification-summary-v1',provider_calls=0,
            rows=[dict(case=r['case'],technical_status=r['technical_status'],reason=r.get('reason')) for r in rows]))
    return rows


if __name__=='__main__':
    main()
