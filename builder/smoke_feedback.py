"""Deterministic bounded smoke feedback; logs explain outcomes, never assign scores."""
import hashlib
import json

VERSION='candidate-smoke-feedback-v1'
MAX_BYTES=16000


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def full_reference(reply):
    raw=encode(reply);sha=hashlib.sha256(raw).hexdigest()
    return dict(path='smoke-report-'+sha+'.json',sha256=sha,bytes=len(raw),
                evidence_reference=reply.get('evidence_reference'))


def compact(reply):
    keys=('status','cause','input_error','native_outcome','working_xml_sha256','smoke_xml_sha256','profile',
          'openmc_version','image_id','processes','statepoint_validation','cleanup_confirmed',
          'coverage','limitations','evidence_reference','elapsed_seconds')
    value={k:reply.get(k) for k in keys}
    value.update(format=VERSION,feedback_complete=True,task_conformity='not_evaluated',
                 full_result=full_reference(reply),full_only=['exact_override_records','longer_log_excerpts','identities'],
                 overrides='Sampling/output scheduling and data-index binding only; see profile and full_result')
    size=1200
    while True:
        value['logs']={}
        for name,log in reply.get('logs',{}).items():
            text=log['text'];clipped=len(text)>size
            excerpt=text if not clipped else text[:size//2]+'\n[omitted middle; read full_result]\n'+text[-size//2:]
            value['logs'][name]=dict(text=excerpt,complete=not clipped and log['complete'],
                                    original_bytes=log['bytes'],sha256=log['sha256'])
        if len(encode(value))<=MAX_BYTES:return value
        if size<=64:break
        size//=2
    # Even unusual metadata cannot silently remove unresolved outcomes/limits.
    return dict(format=VERSION,feedback_complete=False,presentation_cause='feedback_byte_limit',
                status=reply.get('status'),native_outcome=reply.get('native_outcome'),
                full_result=full_reference(reply),instruction='Read full_result before interpreting this incomplete response')
