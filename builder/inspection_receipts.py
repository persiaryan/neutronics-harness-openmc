"""Independent receipt reconstruction for the bounded public adapter output."""
import json
from pathlib import Path
from builder import boundary_tool,openmc_python
from builder.boundary_feedback import compact
from builder.run import verify_container
from evaluator.run import digest
from evaluator.evidence import InsufficientEvidence
from evaluator.transport_input import read_regular
from evaluation.scientific import boundaries
from evaluation.scientific.boundary_scope import SCOPE,LIMITATIONS
from evaluation.scientific.records import require


def verify(directory, *, mode='subscription'):
    directory=Path(directory);read=lambda n:json.loads(read_regular(directory/n))
    require(mode in ('mock','subscription') and read('../manifest.json')['mode']==mode,
            'Adapter verifier requires the declared inference route')
    meta=read('session.json')
    if 'adapter_sha256' not in meta:
        raise InsufficientEvidence('Development adapter execution did not bind its controller source')
    require(meta==dict(session_id=meta['session_id'],owner=meta['owner'],**boundary_tool.identity()),'Adapter semantic identity changed')
    require(read_regular(directory/'adapter.py')==Path(boundary_tool.__file__).read_bytes(),'Adapter controller source changed')
    require(read_regular(directory/'feedback.py')==boundary_tool.FEEDBACK.read_bytes(),'Feedback presentation source changed')
    require(read_regular(directory/'client.py')==boundary_tool.CLIENT.read_bytes() and
            read_regular(directory/'bridge.py')==boundary_tool.BRIDGE.read_bytes(),'Adapter bridge/client changed')
    info=read('container.json');verify_container(info,openmc_python.IMAGE_ID)
    require(meta['owner']==dict(container_id=info['Id'],image_id=info['Image']),'Adapter owner binding changed')
    require(read('client-staging.json')==dict(exit_code=0,stop_reason=None),'Adapter staging incomplete')
    require(read('feedback-staging.json')==dict(exit_code=0,stop_reason=None),'Feedback staging incomplete')
    calls=sorted(directory.glob('call-*'));inspected=0;failed=[]
    require(len(calls)<=3,'Adapter request cap exceeded')
    for number,folder in enumerate(calls,1):
        require(folder.name==f'call-{number:02d}','Adapter call sequence changed')
        request=json.loads(read_regular(folder/'request.json'));reply=json.loads(read_regular(folder/'response.json'))
        require(json.loads(read_regular(folder/'feedback.json'))==compact(reply),'Feedback projection changed')
        common=dict(format=boundary_tool.PROFILE['version'],evidence_reference=f"boundary-inspection:{meta['session_id']}:{number}",
                    scope=SCOPE,limitations=LIMITATIONS,task_conformity='not_evaluated',global_geometry_validity='not_evaluated')
        require(all(reply.get(k)==v for k,v in common.items()),'Adapter public scope changed')
        if reply['status']=='observed':
            require(number<=2 and set(request)=={'tool','xml'} and request['tool']=='inspect_boundaries','Unauthorized inspection')
            xml=read_regular(folder/'model.xml');require(xml==request['xml'].encode(),'Candidate-session XML changed')
            obs=boundaries.record(folder/'inspection',xml)
            expected=dict(common,status='observed',cause=None,artifact_sha256=digest(xml),observations=obs,
                evidence=dict(artifact='candidate-xml:'+digest(xml),observation=common['evidence_reference'],
                    worker_sha256=meta['worker_sha256'],observation_sha256=digest(read_regular(folder/'inspection/stdout.json'))))
            require(reply==expected,'Public adapter reply contradicts observation evidence')
            inspected+=1
        elif reply['cause']=='inspection_evidence_incomplete':
            require(number<=2 and set(request)=={'tool','xml'} and request['tool']=='inspect_boundaries','Unauthorized inspection')
            xml=read_regular(folder/'model.xml');require(xml==request['xml'].encode(),'Candidate-session XML changed')
            failure=boundaries.missing_material_failure(folder/'inspection',xml)
            require(reply==dict(common,status='indeterminate',cause='inspection_evidence_incomplete',
                               observations=None,artifact_sha256=digest(xml)), 'Failure reply contradicts receipts')
            failed.append(dict(call=number,**failure))
        elif reply['cause']=='tool_call_budget_exhausted':
            require(number==3 and reply==dict(common,status='indeterminate',cause='tool_call_budget_exhausted',observations=None),
                    'Unsupported tool-budget claim')
        else:
            raise InsufficientEvidence('This local verifier does not reconstruct the retained failure cause')
    usage=read('usage.json')
    require(usage==dict(attempted_calls=len(calls),artifact_snapshots=inspected+len(failed),started_inspections=inspected+len(failed),maximum_calls=2),
            'Tool-use accounting changed')
    require(read('bridge-cleanup.json')==dict(host_bridge_closed=True,owner_container_removal_required=True,attempted_calls=len(calls)),
            'Bridge closure evidence changed')
    owner=read('../lifecycle.json')
    require(owner['container_id']==meta['owner']['container_id'] and owner['state']=='removed','Builder owner cleanup missing')
    result=dict(evidence_status='coherent',attempted_calls=len(calls),inspections=inspected,
                model_calls=0 if mode=='mock' else read('../result.json')['request_count'],scope=SCOPE,private_comparison='not_exposed')
    if failed:
        result.update(failed_inspections=failed,started_inspections=inspected+len(failed))
    return result
