"""Freeze and qualify the 36-slot A/D pilot. Preparation never calls a provider."""
import argparse
import json
import subprocess
from pathlib import Path

from builder import openmc_python, region_skill, run as builder
from builder.context import request_setup, sha256, write_json
from builder.relay import load_auth, validate_event_stream
from builder.route import condition_prompt, EXTENDED_REQUEST_BUDGET
from evaluation.candidates import run as assessment
from evaluator import run as exporter
from evaluator.profiles import PROFILE, BOUNDARY_PROTOCOL
from evaluator.transport_input import read_regular
from experiments import dashboard_campaign as campaign
from experiments.run import atomic_json
from prompts.prepare import build_prompt, prepare as prepare_prompt

PROTOCOL = Path(__file__).with_name('region_ad_protocol.json')
CASE = 'two_composition_5x5'


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(read_regular(Path(path)))


def protocol():
    raw = PROTOCOL.read_bytes()
    value = json.loads(raw)
    require(value['format'] == 'region-ad-scientific-protocol-v1'
            and value['comparison'] == campaign.REGION_COMPARISON
            and value['arms'] == campaign.REGION_ARMS
            and value['models'] == list(campaign.MODELS)
            and value['cases'] == list(campaign.REGION_TASKS)
            and (value['repeats'], value['assignments'], value['request_limit'],
                 value['authoring_seconds'], value['maximum_model_requests']) == (3,36,16,600,576),
            'A/D scientific protocol does not match its execution design')
    require(value['skill'] == region_skill.material()[1], 'Frozen A/D skill changed')
    return raw, value


def probe_image(image, arguments):
    return builder.docker('run', '--rm', '--network', 'none', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges=true', '--user', '1000:1000',
        '--memory', '1g', '--cpus', '1', '--pids-limit', '64',
        '--tmpfs', '/work:rw,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=700',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=134217728,mode=1777',
        '--entrypoint', arguments[0], image, *arguments[1:])


def dependencies(index):
    """Operator-only hashes and probes, never candidate execution or neutron transport."""
    checks, goals = {}, {}
    def check(name, operation):
        try:
            detail = operation()
            checks[name] = dict(status='passed', detail=detail)
        except (ValueError, RuntimeError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
            checks[name] = dict(status='blocked', error_type=type(error).__name__, reason=str(error)[:500])
    def credentials():
        load_auth(Path.home()/'.codex/auth.json')
        return dict(credentials_available=True, provider_contacted=False)
    check('credentials', credentials)
    def images():
        records = {}
        for image in (openmc_python.IMAGE_ID, PROFILE['export_image'], PROFILE['transport_image']):
            info = json.loads(builder.docker('image','inspect',image))[0]
            require(info['Id'] == image and info['Os'] == 'linux' and info['Architecture'] == 'arm64',
                    'Pinned Linux ARM64 image unavailable')
            if image == openmc_python.IMAGE_ID:
                openmc_python.verify_image(info, True)
            records[image] = dict(os=info['Os'], architecture=info['Architecture'])
        return records
    check('images', images)
    def authoring():
        info = json.loads(probe_image(openmc_python.IMAGE_ID, ['python3','-I','-B','-c',openmc_python.PROBE]))
        openmc_python.verify_probe(info, True)
        return info
    check('authoring_python', authoring)
    def exported():
        result = json.loads(probe_image(PROFILE['export_image'], ['python','-I','-B','-c',
                    'import json,openmc; print(json.dumps(dict(openmc_version=openmc.__version__)))']))
        require(result == dict(openmc_version='0.15.3'), 'Export Python version changed')
        return result
    check('export_python', exported)
    for case in campaign.REGION_TASKS:
        def reference(case=case):
            goal = assessment.target(case)
            require(all(goal['protocol'][k] == PROFILE[k] for k in ('export_image','transport_image')),
                    'Private reference runtime differs from active assessment profile')
            _, result = assessment.preflight(Path(index), goal)
            goals[case] = goal
            return dict(suite_sha256=goal['index']['manifest_sha256'],
                        package_sha256=goal['reference']['manifest_sha256'],
                        technical_status=goal['reference']['technical_status'],
                        grading_enabled=False, data_sha256=sha256(json.dumps(result['data'],sort_keys=True).encode()),
                        required_data_files=len(result['data']['files']))
        check('reference_and_data:'+case, reference)
    def native():
        result = json.loads(probe_image(PROFILE['transport_image'],
                                        ['python','-I','-B','/opt/evaluator/transport_worker.py','probe']))
        require(result['worker_sha256'] == sha256(Path('evaluator/runtime/transport_worker.py').read_bytes()),
                'Native transport worker differs from controller')
        require(len(goals) == 3 and all(result == g['runtime'] for g in goals.values()),
                'Native solver/worker differs from frozen reference identities')
        version = probe_image(PROFILE['transport_image'], ['/opt/openmc/bin/openmc','--version'])
        require(version.startswith('OpenMC version 0.15.3\n'), 'Native solver version changed')
        return result
    check('native_runtime', native)
    return dict(format='region-ad-local-dependencies-v1',
                status='passed' if all(v['status']=='passed' for v in checks.values()) else 'blocked',
                checks=checks, provider_contacted=False, neutron_transport=False,
                scientific_review='pending_owner_review', grading_enabled=False)


def prepare(output, *, index, setups):
    raw, scientific = protocol()
    expected = read(setups)
    require(set(expected) == set(campaign.MODELS), 'Declare the two reviewed A/D model setups')
    for model in campaign.MODELS:
        require(expected[model].get('request_configuration',{}).get('reasoning',{}).get('effort')
                == ('medium' if 'luna' in model else 'low'), 'Unexpected A/D reasoning setup')
    output = Path(output)
    require(not output.exists(), 'Use a fresh A/D campaign directory')
    local = dependencies(index)
    manifest = campaign.prepare_campaign(output, pilot=False, data_index=Path(index),
                    setup_file=Path(setups), comparison=campaign.REGION_COMPARISON)
    (output/'scientific-protocol.json').write_bytes(raw)
    (output/'region-procedure.md').write_bytes(region_skill.material()[0])
    write_json(output/'local-qualification.json', local)
    manifest['region_ad_protocol'] = dict(
        id=scientific['id'], sha256=sha256(raw), skill=scientific['skill'],
        local_qualification_sha256=sha256((output/'local-qualification.json').read_bytes()),
        provider_controls='controls/provider/report.json', native_controls='controls/native/report.json',
        launch_requirements='Current local dependencies, four native A/D controls and four real provider-delivery receipts; no automatic launch')
    atomic_json(output/'manifest.json', manifest)
    (output/'manifest.sha256').write_text(campaign.sha(output/'manifest.json')+chr(10))
    annotations = dict(format='region-ad-annotations-v1', protocol_sha256=sha256(raw),
        campaign_manifest_sha256=campaign.sha(output/'manifest.json'),
        records=[dict(id=r['id'], source_sha256=None, status='pending', reviewer=None,
                      sharing=None, mutation=None, downstream_use=None, damaging_consequence=None,
                      evidence=[], limitations=None) for r in manifest['rows']])
    write_json(output/'annotations-template.json', annotations)
    return manifest


def verify_plan(output):
    output = Path(output)
    manifest = read(output/'manifest.json')
    require((output/'manifest.sha256').read_text().strip() == campaign.sha(output/'manifest.json'),
            'A/D manifest seal changed')
    raw, scientific = protocol()
    binding = manifest['region_ad_protocol']
    require(binding['sha256'] == sha256(raw) and (output/'scientific-protocol.json').read_bytes() == raw,
            'Frozen scientific protocol changed')
    require(binding['skill'] == scientific['skill']
            and (output/'region-procedure.md').read_bytes() == region_skill.material()[0],
            'Frozen A/D procedure changed')
    require(binding['local_qualification_sha256'] == campaign.sha(output/'local-qualification.json'),
            'Local qualification receipt changed')
    require(manifest['comparison'] == campaign.REGION_COMPARISON
            and manifest['arms'] == campaign.REGION_ARMS and manifest['sessions'] == 36
            and manifest['maximum_model_requests'] == 576
            and manifest['source_sha256'] == campaign.sources(), 'Frozen A/D implementation or design changed')
    require(manifest['data_index_sha256'] == campaign.sha(manifest['data_index']), 'Frozen data index changed')
    actual = {(r['model'],r['arm'],r['case'],r['repeat']) for r in manifest['rows']}
    expected = {(m,a,c,r) for m in campaign.MODELS for a in ('A','D')
                for c in campaign.REGION_TASKS for r in (1,2,3)}
    require(len(manifest['rows']) == 36 and actual == expected, 'A/D assignment inventory changed')
    for row in manifest['rows']:
        require(row['path'].startswith('runs/') and '..' not in Path(row['path']).parts,
                'A/D assignment path outside campaign')
        folder = output/row['path']
        require(campaign.sha(folder/'plan.json') == row['plan_sha256'], 'Frozen assignment plan changed')
        plan = read(folder/'plan.json')
        require(plan['model'] == row['model'] and plan['cases'] == [row['case']]
                and plan['assistance'] == campaign.REGION_ARMS[row['arm']]
                and plan['budgets']['model_requests'] == 16 and plan['budgets']['authoring_seconds'] == 600
                and plan['evaluator_protocol'] == BOUNDARY_PROTOCOL, 'A/D assignment contract changed')
        region_skill.verify(folder,plan,plan['assistance'])
    return manifest


def delivery_receipt(folder, model, arm, setup, *, live):
    folder = Path(folder)
    manifest = read(folder/'manifest.json')
    assistance = campaign.REGION_ARMS[arm]
    require(manifest['model'] == model and manifest['assistance'] == assistance
            and manifest['mode'] == ('subscription' if live else 'mock'), 'Control actor/model/arm changed')
    require(manifest['case'] == CASE and manifest['max_requests'] == 1
            and manifest['wall_seconds'] == (120 if live else 60), 'Control task/budget changed')
    region_skill.verify(folder,manifest,assistance)
    prompt = condition_prompt(build_prompt(CASE), assistance, request_budget=EXTENDED_REQUEST_BUDGET)
    request = read(folder/'request-01.json')
    require(region_skill.initial_context(request,prompt,assistance), 'Control initial prompt changed')
    require(request.get('model') == model and request_setup(request) == setup
            and read(folder/'setup-01.json').get('matched') is True, 'Control provider setup changed')
    require({p.name for p in folder.glob('response-*.sse')} == {'response-01.sse'},
            'Control provider response inventory changed')
    response = (folder/'response-01.sse').read_bytes()
    validate_event_stream(response)
    require(read(folder/'result.json')['cleanup_confirmed'] is True, 'Control cleanup uncertain')
    require(manifest['image_id'] == openmc_python.IMAGE_ID
            and manifest['controller_sha256'] == campaign.sha('builder/run.py')
            and campaign.sha(folder/'controller-source.py') == manifest['controller_sha256'],
            'Control controller or image changed')
    if live:
        require({p.name for p in folder.glob('upstream-*.json')} == {'upstream-01.json'},
                'Control upstream request inventory changed')
        upstream = read(folder/'upstream-01.json')
        require(upstream.get('http_status') == 200 and upstream.get('completion_observed') is True
                and upstream.get('stream_validation') == 'passed'
                and upstream.get('response_bytes_forwarded') == len(response)
                and upstream.get('stop_reason') == 'response_completed', 'Provider delivery not demonstrated')
    return dict(model=model, arm=arm, status='passed', provider_contacted=live,
        request_sha256=campaign.sha(folder/'request-01.json'), response_sha256=sha256(response),
        prompt_sha256=sha256(prompt.encode()), setup_sha256=sha256(json.dumps(setup,sort_keys=True).encode()),
        skill_sha256=region_skill.material()[1]['sha256'] if arm=='D' else None)


def controls(output, *, live=False):
    manifest = verify_plan(output)
    output = Path(output)
    kind = 'provider' if live else 'native'
    root = output/'controls'/kind
    root.mkdir(parents=True, exist_ok=False)
    prepare_prompt(CASE,root/'input')
    report = dict(format='region-ad-controls-v1', kind=kind, status='running',
                  protocol_sha256=manifest['region_ad_protocol']['sha256'], rows=[],
                  maximum_provider_requests=4 if live else 0, excluded_from_pilot=True)
    write_json(root/'report.json',report)
    from tests.fixtures.responses import mock_response
    for model in campaign.MODELS:
        for arm in ('A','D'):
            folder = root/(model+'-'+arm)
            try:
                result = builder.run(folder,case=CASE,prepared_input=root/'input',model=model,
                    assistance=campaign.REGION_ARMS[arm], mode='subscription' if live else 'mock',
                    responder=None if live else lambda *_:mock_response(),
                    max_requests=1,wall_seconds=120 if live else 60,
                    request_budget=EXTENDED_REQUEST_BUDGET,request_setup=manifest['request_setups'][model],
                    expected_region_skill=region_skill.material()[1] if arm=='D' else None)
                receipt = delivery_receipt(folder,model,arm,manifest['request_setups'][model],live=live)
            except (ValueError, OSError, KeyError, RuntimeError, subprocess.SubprocessError):
                report.update(status='blocked', stopped_at=folder.name,
                              reason='Required delivery evidence unavailable; inspect retained control; no retry')
                write_json(root/'report.json',report)
                return report
            report['rows'].append(dict(receipt, directory=folder.name, builder_status=result['status']))
            write_json(root/'report.json',report)
    report['status']='passed'
    write_json(root/'report.json',report)
    return report


def readiness(output):
    manifest = verify_plan(output)
    output = Path(output)
    local = dependencies(manifest['data_index'])
    frozen = read(output/'local-qualification.json')
    fixed = lambda report: {k:v.get('detail') for k,v in report.get('checks',{}).items() if k!='credentials'}
    statuses = dict(local_dependencies=local['status'], frozen_dependency_identity=(
        'passed' if frozen['status']=='passed' and fixed(local)==fixed(frozen) else 'blocked'))
    for kind in ('native','provider'):
        path = output/'controls'/kind/'report.json'
        try:
            report = read(path)
            require(report['status']=='passed' and report['kind']==kind
                    and report['protocol_sha256']==manifest['region_ad_protocol']['sha256'],
                    'Control report incomplete or incompatible')
            require(len(report['rows'])==4 and {(r['model'],r['arm']) for r in report['rows']} ==
                    {(m,a) for m in campaign.MODELS for a in ('A','D')}, 'Control matrix incomplete')
            for row in report['rows']:
                require(row['directory']==row['model']+'-'+row['arm'], 'Control path changed')
                proof = delivery_receipt(path.parent/row['directory'],row['model'],row['arm'],
                        manifest['request_setups'][row['model']],live=kind=='provider')
                require(all(row.get(k)==v for k,v in proof.items()), 'Control receipt changed')
            statuses[kind+'_controls']='passed'
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            statuses[kind+'_controls']='blocked'
    return dict(format='region-ad-readiness-v1',
                status='ready' if all(v=='passed' for v in statuses.values()) else 'blocked',
                checks=statuses, local=local, pilot_dispatched=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','qualify-native','probe-provider','check'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--data-index',type=Path)
    parser.add_argument('--setups',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':
        if not args.data_index or not args.setups: parser.error('Preparation requires --data-index and --setups')
        value=prepare(args.output,index=args.data_index,setups=args.setups)
        value=dict(status='prepared_not_dispatched',sessions=value['sessions'],maximum_model_requests=value['maximum_model_requests'])
    elif args.action=='check':
        value=readiness(args.output)
        atomic_json(args.output/'readiness.json',value)
    else:
        value=controls(args.output,live=args.action=='probe-provider')
    print(json.dumps(value,indent=2))
