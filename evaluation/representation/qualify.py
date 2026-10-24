"""Run independent XML controls in isolated OpenMC workers; no campaign input."""
import argparse
import json
from pathlib import Path

from evaluator.run import digest, write_json
from evaluator.transport_input import read_regular
from evaluation.scientific import boundaries, inspection
from evaluation.scientific import source_domains
from evaluation.scientific.records import require
from evaluation.representation import controls


def boundary_verdict(result):
    values = [v['verdict'] for v in result['verdicts']]
    if 'nonconforming' in values:
        return 'nonconforming'
    return 'conformity_established' if values and all(v=='conformity_established' for v in values) else 'indeterminate'


def boundary_row(control,obs,result,witness_state):
    verdict=boundary_verdict(result)
    passed=(verdict==control['expected'] if control['expected']!='geometry_overlap' else witness_state=='overlap')
    if control['id'] in ('missing-lower-slab','interior-water-hole'): passed=passed and witness_state=='outside'
    if control['id'] in ('unbounded-lower-water','moved-face'): passed=passed and witness_state=='ok'
    return dict(id=control['id'],xml_sha256=digest(control['xml']),expected=control['expected'],actual=verdict,
                witness_state=witness_state,passed=passed,domain=obs['domain'],analysis=obs['coverage']['analysis'])


def source_row(control,comparison):
    return dict(id=control['id'],xml_sha256=digest(control['xml']),expected=control['expected'],actual=comparison['passed'],
                passed=comparison['passed'] is control['expected'],proof=comparison['proof'],cause=comparison['cause'])


def verify(output,*,family):
    import xml.etree.ElementTree as ET
    output=Path(output);report=json.loads(read_regular(output/'report.json'));rows=[]
    require(report['provider_calls']==0 and report['original_outcomes_reassessed'] is False,'Qualification scope changed')
    image=report['image']
    if family=='boundary':
        require(report['format']=='representation-boundary-qualification-v1' and report['campaign_candidates']==0,
                'Unknown boundary qualification')
        version=report['observer_version'];spec=controls.specification()
        require(json.loads(read_regular(output/'requirements.json'))==spec,'Control requirements changed')
        require(report['worker_sha256']==digest(boundaries.WORKER.with_name('boundary_worker_'+version.rsplit('-',1)[1]+'.py').read_bytes()),
                'Qualification worker identity changed')
        fixtures=controls.boundary_controls()
    else:
        require(report['format']=='source-domain-qualification-v1' and
                report['worker_sha256']==digest(inspection.WORKER.with_name('source_domains_worker_v1.py').read_bytes()),
                'Source qualification worker identity changed')
        fixtures=controls.source_controls()
    for control in fixtures:
        folder=output/control['id'];xml=read_regular(folder/'model.xml')
        require(xml==control['xml'],'Control XML changed')
        if family=='boundary':
            obs=boundaries.record(folder/'boundaries',xml,image=image,version=version)
            comparison=boundaries.compare(obs,spec);witness_state=None
            if control['witness'] is not None:
                witness=inspection.completed_record(folder/'witness',xml,[control['witness']],image=image)
                witness_state=witness['observations'][0][0]
            rows.append(boundary_row(control,obs,comparison,witness_state))
        else:
            obs=source_domains.record(folder/'inspection',xml,controls.SOURCE_POINTS,image=image)
            comparison=source_domains.compare(ET.fromstring(xml),obs,control['material_fissionability'])
            rows.append(source_row(control,comparison))
        require(comparison==json.loads(read_regular(folder/'comparison.json')),'Control comparison changed')
    require(report['rows']==rows and report['status']==('passed' if all(r['passed'] for r in rows) else 'failed'),
            'Qualification summary contradicts retained observations')
    return dict(status='verified_controls',family=family,controls=len(rows),requirements_met=report['status']=='passed',
                report_sha256=digest(read_regular(output/'report.json')))


def run(output, *, version=boundaries.NEXT_VERSION, image=inspection.IMAGE):
    output=Path(output); output.mkdir(parents=True, exist_ok=False)
    specification=controls.specification()
    write_json(output/'requirements.json', specification)
    report=dict(format='representation-boundary-qualification-v1', observer_version=version,
                image=image, provider_calls=0, campaign_candidates=0, original_outcomes_reassessed=False,
                controls_sha256=digest(Path(controls.__file__).read_bytes()),
                worker_sha256=digest(boundaries.WORKER.with_name('boundary_worker_'+version.rsplit('-',1)[1]+'.py').read_bytes()),
                rows=[], status='running')
    write_json(output/'report.json', report)
    try:
        for control in controls.boundary_controls():
            folder=output/control['id']; folder.mkdir()
            xml=control['xml']; (folder/'model.xml').write_bytes(xml)
            print(json.dumps(dict(control=control['id'], event='started')), flush=True)
            boundaries.observe(xml, folder/'boundaries', image=image, version=version)
            obs=boundaries.record(folder/'boundaries', xml, image=image, version=version)
            result=boundaries.compare(obs, specification)
            verdict=boundary_verdict(result)
            witness_state=None
            if control['witness'] is not None:
                # The retained standard inspector receives a literal independent
                # witness; it is not asked to prove equivalence from sampling.
                value=inspection.inspect_xml(xml, [control['witness']], folder/'witness', image=image)
                require(value['status']=='inspected' and value['cleanup_confirmed'], 'Witness inspection failed')
                value=inspection.completed_record(folder/'witness', xml, [control['witness']], image=image)
                witness_state=value['observations'][0][0]
            row=boundary_row(control,obs,result,witness_state)
            report['rows'].append(row)
            write_json(folder/'comparison.json', result)
            write_json(output/'report.json', report)
            print(json.dumps(dict(control=control['id'], event='finished', passed=row['passed'], actual=verdict)), flush=True)
        report['status']='passed' if all(r['passed'] for r in report['rows']) else 'failed'
    except Exception as exc:
        report.update(status='blocked', error_type=type(exc).__name__, reason=str(exc))
        raise
    finally:
        write_json(output/'report.json', report)
    return report


def run_sources(output, *, image=inspection.IMAGE):
    import xml.etree.ElementTree as ET
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report=dict(format='source-domain-qualification-v1',image=image,provider_calls=0,
                original_outcomes_reassessed=False,rows=[],status='running',
                worker_sha256=digest(inspection.WORKER.with_name('source_domains_worker_v1.py').read_bytes()))
    write_json(output/'report.json',report)
    try:
        for control in controls.source_controls():
            folder=output/control['id'];folder.mkdir()
            xml=control['xml'];(folder/'model.xml').write_bytes(xml)
            print(json.dumps(dict(control=control['id'],event='started')),flush=True)
            source_domains.observe(xml,controls.SOURCE_POINTS,folder/'inspection',image=image)
            obs=source_domains.record(folder/'inspection',xml,controls.SOURCE_POINTS,image=image)
            comparison=source_domains.compare(ET.fromstring(xml),obs,control['material_fissionability'])
            write_json(folder/'comparison.json',comparison)
            row=source_row(control,comparison)
            report['rows'].append(row);write_json(output/'report.json',report)
            print(json.dumps(row),flush=True)
        report['status']='passed' if all(r['passed'] for r in report['rows']) else 'failed'
    except Exception as exc:
        report.update(status='blocked',error_type=type(exc).__name__,reason=str(exc))
        raise
    finally:
        write_json(output/'report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--observer', choices=['v2','v3'], default='v3')
    parser.add_argument('--family', choices=['boundary','source'], default='boundary')
    parser.add_argument('--verify', action='store_true')
    args=parser.parse_args()
    if args.verify:
        print(json.dumps(verify(args.output,family=args.family)))
        return 0
    report=(run_sources(args.output) if args.family=='source' else
            run(args.output, version='effective-boundary-observation-'+args.observer))
    print(json.dumps(dict(status=report['status'], controls=len(report['rows']))))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
