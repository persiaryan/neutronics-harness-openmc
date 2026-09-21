"""Read independently retained scientific evidence; no reference/candidate imports."""
import json
import math
import re
from pathlib import Path
from evaluator.run import digest
from evaluator.transport_input import read_regular
from evaluator.evidence import InsufficientEvidence
def require(condition, message):
    if not condition:
        raise ValueError(message)

def reader(directory):
    directory = Path(directory).absolute()
    require(not directory.is_symlink(), 'Evidence directory must not be a symlink')
    receipts = {}
    def read(name):
        path = directory/name
        require(not path.parent.is_symlink(), 'Evidence parent must not be a symlink')
        data = read_regular(path, limit=32_000_000)
        receipts[str(path)] = {'sha256':digest(data),'bytes':len(data)}
        return data
    return read, receipts

def validate_keff(value):
    for key in ('mean','std_dev'):
        require(type(value[key]) in (int,float) and math.isfinite(value[key]) and value[key] > 0,
                'Invalid k-effective or standard deviation')
    require(value['uncertainty'] == 'one sigma', 'Unsupported uncertainty convention')
    return {key:value[key] for key in ('mean','std_dev','uncertainty')}

def unchanged(receipts):
    for path, record in receipts.items():
        data = read_regular(Path(path),limit=32_000_000)
        require(record == {'sha256':digest(data),'bytes':len(data)}, 'Evidence changed during report: '+path)
def close(a, b):
    # Serialization/arithmetic tolerance only, not a physics acceptance margin.
    return math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10)
def inspection_record(case, directory, xml, worker):
    """Verify completed observations OR a retained failure; never assume success."""
    from evaluation.benchmark_suite.suite_cases import probes
    from evaluation.scientific.inspection import verify, admit, IMAGE
    def read(name):return read_regular(directory/name)
    manifest=json.loads(read('manifest.json'));raw=read('input.json');payload=json.loads(raw)
    require(manifest['format']=='private-scientific-inspection-v2' and manifest['model_xml_sha256']==digest(xml), 'Inspection XML/version changed')
    require(manifest['image_id']==IMAGE and manifest['candidate_python_access'] is False and
            manifest['nuclear_data_access'] is False and manifest['host_mounts'] is False and
            manifest['native_transport']=='not_run', 'Inspector execution boundary changed')
    require(manifest['input_sha256']==digest(raw) and payload['xml'].encode()==xml and payload['points']==probes(case)[0], 'Inspection input/probes changed')
    require(read('worker.py')==worker and manifest['worker_sha256']==digest(worker), 'Inspector worker changed')
    require(all(json.loads(read('container-checks.json')).values()), 'Inspector boundary failed')
    verify(json.loads(read('container-inspect.json')))
    execution=json.loads(read('execution.json'))
    raw=read('stdout.json');read('stderr.txt')
    result=json.loads(read('result.json'))
    if result['cleanup_confirmed'] is not True:
        raise InsufficientEvidence('Inspector cleanup is not confirmed')
    require(type(execution['exit_code']) is int and execution['stop_reason'] in (None,'timeout','output_limit'),
            'Malformed inspector process outcome')
    if execution['exit_code']!=0 or execution['stop_reason'] is not None:
        require(result['status']=='infrastructure_failure' and 'findings' not in result,
                'Incomplete inspector process promoted to observations or candidate failure')
        return result
    try:
        stdout=json.loads(raw)
    except (ValueError, UnicodeError):
        require(result['status']=='infrastructure_failure', 'Unreadable output promoted to observations')
        raise InsufficientEvidence('Inspector output is unreadable; no qualified observation')
    require(isinstance(stdout,dict) and all(result.get(k)==v for k,v in stdout.items()), 'Inspector result changed')
    require(stdout['status'] in ('inspected','invalid_model','unsupported_or_invalid'), 'Unknown inspector outcome')
    if stdout['status']=='invalid_model':
        require(set(stdout)=={'status','openmc_version','findings'} and stdout['openmc_version']=='0.15.3',
                'Unqualified material-failure observation')
        # Independently check this narrow native-input precondition against the
        # admitted bytes. No density calculation, physical repair or private target.
        root=admit(xml)
        expected=[dict(code='material_requires_nuclides_or_macroscopic', material_id=int(m.get('id')),
                       nuclide_count=0, macroscopic_present=False)
                  for m in root.findall('materials/material')
                  if not m.findall('nuclide') and m.find('macroscopic') is None]
        require(expected and stdout['findings']==expected, 'Material rejection contradicts admitted XML')
    elif stdout['status']=='unsupported_or_invalid':
        require(set(stdout)=={'status','error_type','error'} and
                isinstance(stdout['error_type'],str) and isinstance(stdout['error'],str) and
                'findings' not in result, 'Unqualified inspector error')
    else:
        require('findings' not in result, 'Successful inspection claims input rejection')
    return result

def leakage(log):
    values=re.findall(r'Leakage Fraction\s*=\s*([\d.eE+\-]+)\s*\+/-\s*([\d.eE+\-]+)',log)
    require(len(values)==1, 'Missing or ambiguous native leakage diagnostic')
    mean,sigma=map(float,values[0])
    require(math.isfinite(mean) and math.isfinite(sigma), 'Nonfinite leakage')
    return dict(mean=mean,std_dev=sigma,precision='Native stdout rounded values, not a new scored observable')
