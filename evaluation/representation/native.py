"""Bounded source-law and coincident-face native controls, separate from grading."""
import argparse
import json
import math
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

from evaluator import run, transport
from evaluator.profiles import PROFILE
from evaluator.transport_input import read_regular
from evaluation.scientific.inspection import admit
from evaluation.scientific.records import require
from evaluation.representation import controls

WORKER=Path(__file__).with_name('native_worker.py')
IMAGE=PROFILE['transport_image']
TMPFS={'/tmp':'rw,nosuid,nodev,size=268435456,uid=1000,gid=1000,mode=700'}


def verify_container(info):
    h,c=info['HostConfig'],info['Config']
    mounts=info['Mounts']
    require(info['Image']==IMAGE and c['User']=='1000:1000' and c['Entrypoint']==['python'], 'Native control identity changed')
    require(c['Cmd']==['-I','-B','-c','import time; time.sleep(3600)'], 'Native idle command changed')
    require('OMP_NUM_THREADS=1' in c['Env'], 'Native thread limit changed')
    require(h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and h['Privileged'] is False and
            h['CapDrop']==['ALL'] and not h.get('CapAdd') and not h.get('Devices') and
            'no-new-privileges=true' in h['SecurityOpt'] and h.get('PidMode','')=='' and h['IpcMode']=='private' and
            h['Memory']==3*1024**3 and h['NanoCpus']==2_000_000_000 and h['PidsLimit']==128 and
            h['Tmpfs']==TMPFS and h['LogConfig']['Type']=='none', 'Native control containment changed')
    require(len(mounts)==1 and mounts[0]['Destination']=='/data' and mounts[0]['RW'] is False and
            mounts[0]['Type']=='bind', 'Only read-only nuclear data may be mounted')
    return dict(containment_verified=True,source=mounts[0]['Source'])


def input_xml(xml,index):
    root=ET.fromstring(xml)
    for node in root.findall('materials/cross_sections'): root.find('materials').remove(node)
    ET.SubElement(root.find('materials'),'cross_sections').text='/data/'+index.name
    for node in root.findall('settings/verbosity'): root.find('settings').remove(node)
    ET.SubElement(root.find('settings'),'verbosity').text='0'
    return ET.tostring(root)


def record(folder,index,*,expected_xml,mode):
    """Read-only reconstruction; edited or incomplete receipts grant no credit."""
    folder=Path(folder);index=Path(index).resolve(strict=True)
    read=lambda name:json.loads(read_regular(folder/name))
    xml=read_regular(folder/'model.xml');manifest=read('manifest.json')
    require(xml==input_xml(expected_xml,index),'Native control XML changed')
    require(manifest==dict(format='native-representation-control-v1',image=IMAGE,worker_sha256=run.digest(WORKER.read_bytes()),
        input_sha256=run.digest(read_regular(folder/'input.json')),model_xml_sha256=run.digest(xml),wall_seconds=120,
        mode=mode,candidate_python_access=False,reference_access=False,automatic_retries=0,
        data_directory=str(index.parent.resolve())),'Native control manifest changed')
    require(read_regular(folder/'worker.py')==WORKER.read_bytes(),'Native control worker changed')
    require(read('input.json')==dict(xml=xml.decode(),mode=mode,samples=4096,seed=41),'Native control query changed')
    info=read('container.json');verified=verify_container(info)
    require(verified==read('container-checks.json') and
            verified['source'].removeprefix('/host_mnt')==str(index.parent.resolve()),'Native data mount changed')
    root=ET.fromstring(xml)
    tables=sorted({('neutron',n.get('name')) for n in root.findall('materials/material/nuclide')})
    require(read('data-before.json')==read('data-after.json')==transport.data_identity(index,dict(required_tables=tables)),
            'Native data bytes changed')
    execution=read('execution.json');result=read('result.json')
    require(result.get('cleanup_confirmed') is True,'Native control cleanup is not confirmed')
    if execution==dict(exit_code=0,stop_reason=None):
        stdout=json.loads(read_regular(folder/'stdout.txt'))
        require(result==dict(stdout,cleanup_confirmed=True) and stdout['openmc_version']=='0.15.3' and
                stdout['mode']==mode and stdout['model_xml_sha256']==run.digest(xml),'Native result/input binding changed')
        require(set(stdout['native_files'])=={'/opt/openmc/bin/openmc','/opt/openmc/lib/libopenmc.so'} and
                stdout['python_binding_sha256'],'Native runtime evidence missing')
        if mode=='sample':
            points=stdout['positions']
            require(stdout['status']=='sampled' and stdout['seed']==41 and len(points)==4096 and
                    all(len(p)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in p) for p in points),
                    'Invalid native source samples')
        else:
            require(stdout['status']=='transport_completed' and all(type(v) in (int,float) and math.isfinite(v)
                    for v in stdout['leakage'].values()),'Invalid native crossing result')
    else:
        require(result==dict(status='native_process_failed',execution=execution,cleanup_confirmed=True),
                'Native failure promoted to a completed observation')
    return result


def lost_particle_failure(folder,result):
    return (result['status']=='native_process_failed' and result['execution']==dict(exit_code=255,stop_reason=None)
            and 'Maximum number of lost particles has been reached' in
            read_regular(Path(folder)/'stderr.txt').decode(errors='replace'))


def execute(xml, folder, index, mode):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    admit(xml)
    # Data paths are explicit control setup, never a change to a campaign model.
    original=xml;xml=input_xml(xml,index);root=ET.fromstring(xml)
    (folder/'model.xml').write_bytes(xml)
    tables=sorted({('neutron',n.get('name')) for n in root.findall('materials/material/nuclide')})
    data=transport.data_identity(index,dict(required_tables=tables))
    run.write_json(folder/'data-before.json',data)
    worker=WORKER.read_bytes();(folder/'worker.py').write_bytes(worker)
    payload=dict(xml=xml.decode(),mode=mode,samples=4096,seed=41)
    raw=json.dumps(payload,separators=(',',':')).encode();(folder/'input.json').write_bytes(raw)
    manifest=dict(format='native-representation-control-v1',image=IMAGE,worker_sha256=run.digest(worker),
                  input_sha256=run.digest(raw),model_xml_sha256=run.digest(xml),wall_seconds=120,
                  mode=mode,candidate_python_access=False,reference_access=False,automatic_retries=0,
                  data_directory=str(index.parent.resolve()))
    run.write_json(folder/'manifest.json',manifest)
    name='neutronics-representation-'+uuid.uuid4().hex[:12]
    result=dict(status='incomplete',cleanup_confirmed=False)
    attempted=False
    try:
        require(json.loads(run.docker('image','inspect',IMAGE))[0]['Id']==IMAGE,'Native image unavailable')
        attempted=True
        run.docker('create','--name',name,'--network','none','--read-only','--user','1000:1000',
            '--cap-drop','ALL','--security-opt','no-new-privileges=true','--pids-limit','128','--memory','3g','--cpus','2',
            '--log-driver','none','--tmpfs','/tmp:'+TMPFS['/tmp'],
            '--mount',f'type=bind,source={index.parent.resolve()},target=/data,readonly',
            '--env','OMP_NUM_THREADS=1','--entrypoint','python',IMAGE,'-I','-B','-c','import time; time.sleep(3600)')
        info=json.loads(run.docker('inspect',name))[0]
        run.write_json(folder/'container.json',info)
        run.write_json(folder/'container-checks.json',verify_container(info))
        run.docker('start',name)
        executed=run.bounded(['docker','exec','-i',name,'python','-I','-B','-c',worker.decode()],
                             timeout=120,limit=2_000_000,data=raw)
        stdout=executed.pop('stdout');stderr=executed.pop('stderr')
        (folder/'stdout.txt').write_bytes(stdout);(folder/'stderr.txt').write_bytes(stderr)
        run.write_json(folder/'execution.json',executed)
        if executed==dict(exit_code=0,stop_reason=None):
            result.update(json.loads(stdout))
        else:
            result.update(status='native_process_failed',execution=executed)
    finally:
        if attempted and run.docker('ps','-aq','--filter','name=^/'+name+'$'):
            run.docker('rm','-f',name)
        result['cleanup_confirmed']=not run.docker('ps','-aq','--filter','name=^/'+name+'$')
        after=transport.data_identity(index,dict(required_tables=tables))
        run.write_json(folder/'data-after.json',after)
        run.write_json(folder/'result.json',result)
        require(after==data and result['cleanup_confirmed'],'Native control data/cleanup changed')
    return record(folder,index,expected_xml=original,mode=mode)


def crossing_xml(control):
    root=ET.fromstring(control['xml'])
    for c in root.findall('geometry/cell'): c.set('material','void')
    # No material collisions: every history must travel straight to the lower face.
    m=root.find('materials');m[:]=[]
    material=ET.SubElement(m,'material',id='1')
    ET.SubElement(material,'density',units='g/cm3',value='1')
    ET.SubElement(material,'nuclide',name='H1',ao='1')
    s=root.find('settings');s[:]=[]
    for tag,value in [('run_mode','fixed source'),('particles','10'),('batches','2'),('seed','41')]:
        ET.SubElement(s,tag).text=value
    src=ET.SubElement(s,'source',type='independent')
    space=ET.SubElement(src,'space',type='point');ET.SubElement(space,'parameters').text='0 0 0'
    ET.SubElement(src,'angle',type='monodirectional',reference_uvw='0 0 -1')
    energy=ET.SubElement(src,'energy',type='discrete');ET.SubElement(energy,'parameters').text='1000000 1'
    return ET.tostring(root)


def source_row(control,result,baseline):
    require(result['status']=='sampled','Native source sampling did not complete')
    positions=result['positions'];require(len(positions)==4096,'Wrong sample count')
    fuel=lambda p:(-.8<p[0]<-.2 or .2<p[0]<.8) and abs(p[1])<1 and abs(p[2])<1
    counts=dict(fuel=sum(map(fuel,positions)),left=sum(p[0]<-.2 for p in positions),
                outside_box=sum(not(-1<p[0]<1 and abs(p[1])<.9 and abs(p[2])<.9) for p in positions))
    positions_hash=run.digest(json.dumps(positions,separators=(',',':')).encode())
    if control['expected'] is True:
        passed=(counts['fuel']==4096 and counts['outside_box']==0 and
                .35<counts['left']/4096<.65 and (baseline is None or positions_hash==baseline))
    elif control['id']=='missing-fuel-cell': passed=counts['fuel']==counts['left']==4096
    elif control['id'] in ('water-domain','same-id-now-water'): passed=counts['fuel']==0
    else: passed=0<counts['fuel']<4096
    return dict(id=control['id'],counts=counts,positions_sha256=positions_hash,passed=passed)


def crossing_row(control,result,folder):
    lost=lost_particle_failure(folder,result)
    completed=(result['status']=='transport_completed' and result['leakage']['mean']==1. and result['leakage']['std_dev']==0.)
    passed=completed if 'vacuum' in control['id'] else completed or lost
    return dict(id=control['id'],native_status=result['status'],passed=passed,
                observer_expected=control['expected'],conformity_inferred_from_transport=False)


def verify(output,index):
    output=Path(output);report=json.loads(read_regular(output/'report.json'))
    expected=dict(format='native-representation-qualification-v1',source_rows=[],crossing_rows=[],
                  provider_calls=0,campaign_candidates=0,status='passed')
    baseline=None;native_identity=None
    for control in controls.source_controls():
        if control['expected'] is None or control['id']=='known-omission-with-unknown': continue
        result=record(output/control['id'],index,expected_xml=control['xml'],mode='sample')
        identity=(result['native_files'],result['python_binding_sha256'])
        if native_identity is None: native_identity=identity
        require(identity==native_identity,'Native runtime changed between controls')
        row=source_row(control,result,baseline)
        if control['id']=='fissionable-flag': baseline=row['positions_sha256']
        expected['source_rows'].append(row)
    for control in controls.boundary_controls():
        if not control['id'].startswith('coincident-'): continue
        result=record(output/control['id'],index,expected_xml=crossing_xml(control),mode='crossing')
        if result['status']=='transport_completed':
            require((result['native_files'],result['python_binding_sha256'])==native_identity,'Native crossing runtime changed')
        expected['crossing_rows'].append(crossing_row(control,result,output/control['id']))
    require(all(r['passed'] for r in expected['source_rows']+expected['crossing_rows']) and report==expected,
            'Native qualification report contradicts retained execution')
    return dict(status='verified_native_controls',source_controls=len(expected['source_rows']),
                crossing_controls=len(expected['crossing_rows']),report_sha256=run.digest(read_regular(output/'report.json')))


def qualify(output,index):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);index=Path(index).resolve(strict=True)
    index,_=run.data_directory(index)
    report=dict(format='native-representation-qualification-v1',source_rows=[],crossing_rows=[],
                provider_calls=0,campaign_candidates=0,status='running')
    run.write_json(output/'report.json',report)
    try:
        baseline=None
        for control in controls.source_controls():
            if control['expected'] is None or control['id']=='known-omission-with-unknown': continue
            print(json.dumps(dict(control=control['id'],mode='sample',event='started')),flush=True)
            result=execute(control['xml'],output/control['id'],index,'sample')
            row=source_row(control,result,baseline)
            if control['id']=='fissionable-flag': baseline=row['positions_sha256']
            report['source_rows'].append(row);run.write_json(output/'report.json',report)
            print(json.dumps(row),flush=True)
        for control in controls.boundary_controls():
            if not control['id'].startswith('coincident-'): continue
            print(json.dumps(dict(control=control['id'],mode='crossing',event='started')),flush=True)
            result=execute(crossing_xml(control),output/control['id'],index,'crossing')
            # Conflicts are observations, not reinterpreted as conformity.
            row=crossing_row(control,result,output/control['id'])
            report['crossing_rows'].append(row);run.write_json(output/'report.json',report)
            print(json.dumps(row),flush=True)
        report['status']='passed' if all(r['passed'] for r in report['source_rows']+report['crossing_rows']) else 'failed'
    except Exception as exc:
        report.update(status='blocked',error_type=type(exc).__name__,reason=str(exc));raise
    finally:
        run.write_json(output/'report.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--data-index',type=Path,required=True)
    p.add_argument('--verify',action='store_true')
    args=p.parse_args();result=verify(args.output,args.data_index) if args.verify else qualify(args.output,args.data_index)
    print(json.dumps(result if args.verify else dict(status=result['status'])))
    raise SystemExit(0 if result['status'] in ('passed','verified_native_controls') else 1)
