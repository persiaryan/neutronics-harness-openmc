"""Candidate-session-only boundary adapter. No task comparison or scoring.

The controller binds this object to one verified container. Requests supply XML
bytes through that container's stdio bridge, never a host path or artifact ID
belonging to another session. Every accepted request gets a fresh XML inspector.
"""
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import threading
import uuid
import time
from observability import now, tool_observation

from evaluation.scientific import boundaries
from evaluation.scientific.boundary_scope import SCOPE, LIMITATIONS
from evaluation.scientific.inspection import admit
from evaluator.run import write_json, bounded
from builder import boundary_feedback

CONDITION='codex_factory_boundary_inspection_v2'
PROFILE=dict(version='candidate-boundary-tool-v2',max_calls=2,max_xml_bytes=500000,
             max_recorded_requests=3,
             inspection_seconds=120,minimum_session_seconds_to_start=180,
             staging_seconds=30,bridge_start_seconds=10,response_bytes=1800000)
CLIENT=Path(__file__).with_name('boundary_client.py')
BRIDGE=Path(__file__).with_name('boundary_bridge.py')
FEEDBACK=Path(boundary_feedback.__file__)
INSTRUCTION='''
Candidate artifact inspection capability (separate experimental condition):
You may inspect your own exported combined model.xml by running:
python3 /work/inspect_boundaries.py model.xml
Paths must be regular files below /work/workspace, without links or parent traversal.
The tool runs a fresh XML-only OpenMC boundary observer. It returns effective
properties, possible face contributors, coverage, limitations and evidence IDs.
It has no reference answers, task comparator or score and performs no repair.
The default candidate-boundary-feedback-v1 JSON preserves domain/face observations,
effective properties, coverage, all limitations and unresolved observation causes.
feedback_complete describes presentation, not scientific conformity. Print the
entire default reply. Full surface records are saved once at full_result.path;
read that JSON with ordinary Python for details, without another inspection.
If feedback_complete is false, omitted sections are explicit: read the saved
report before interpreting them. Do not rerun inspection to recover output.
Only uniform open root-box face behavior is qualified. Mixed face behavior,
curved exteriors and unresolved hierarchy must not be interpreted as passing.
At most two calls are available; every attempted request consumes a call. Export
XML locally if you want to use it. Tool availability does not require tool use.
The final deliverable is still only the requested Python factory module.
'''


def identity():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    return dict(condition=CONDITION,profile=PROFILE,observer=boundaries.VERSION,scope=SCOPE,
                feedback_format=boundary_feedback.VERSION,feedback_max_bytes=boundary_feedback.MAX_BYTES,
                feedback_sha256=sha(FEEDBACK),
                adapter_sha256=sha(Path(__file__)),
                worker_sha256=sha(boundaries.WORKER),client_sha256=sha(CLIENT),bridge_sha256=sha(BRIDGE),
                private_reference_access=False,comparison=False,scoring=False,automatic_repair=False)


class Session:
    """Only the trusted launcher creates a session and supplies its owner binding."""
    def __init__(self, output, owner):
        self.output=Path(output);self.output.mkdir(parents=True,exist_ok=False)
        self.owner=owner;self.id=uuid.uuid4().hex;self.calls=0
        (self.output/'adapter.py').write_bytes(Path(__file__).read_bytes())
        (self.output/'feedback.py').write_bytes(FEEDBACK.read_bytes())
        write_json(self.output/'session.json',dict(session_id=self.id,owner=owner,**identity()))
        write_json(self.output/'usage.json',dict(attempted_calls=0,artifact_snapshots=0,started_inspections=0,
                                               maximum_calls=PROFILE['max_calls']))

    def inspect_boundaries(self, request, *, remaining_seconds):
        if self.calls>=PROFILE['max_recorded_requests']:
            raise ValueError('Boundary tool request budget already exhausted')
        self.calls+=1
        folder=self.output/f'call-{self.calls:02d}';folder.mkdir()
        observed_start, observed_clock = now(), time.monotonic()
        reference=f'boundary-inspection:{self.id}:{self.calls}'
        write_json(folder/'request.json',request)
        response=dict(format=PROFILE['version'],evidence_reference=reference,status='indeterminate',
                      cause=None,observations=None,scope=SCOPE,limitations=LIMITATIONS,
                      task_conformity='not_evaluated',global_geometry_validity='not_evaluated')
        try:
            if self.calls>PROFILE['max_calls']:
                response['cause']='tool_call_budget_exhausted';return response
            if remaining_seconds<PROFILE['minimum_session_seconds_to_start']:
                response['cause']='insufficient_remaining_session_budget';return response
            if not isinstance(request,dict) or set(request)!={'tool','xml'} or request['tool']!='inspect_boundaries' or not isinstance(request['xml'],str):
                response['cause']='invalid_request';return response
            xml=request['xml'].encode('utf-8')
            if not 0<len(xml)<=PROFILE['max_xml_bytes']:
                response['cause']='artifact_byte_limit';return response
            (folder/'model.xml').write_bytes(xml)
            sha=hashlib.sha256(xml).hexdigest();response['artifact_sha256']=sha
            try:admit(xml)
            except Exception:
                response['cause']='artifact_not_admitted';return response
            execution=boundaries.observe(xml,folder/'inspection',wall_seconds=PROFILE['inspection_seconds'])
            if execution.get('cleanup_confirmed') is not True:
                response['cause']='inspection_cleanup_uncertain';return response
            try:obs=boundaries.record(folder/'inspection',xml)
            except Exception:
                response['cause']='inspection_evidence_incomplete';return response
            response.update(status='observed',observations=obs,
                evidence=dict(artifact='candidate-xml:'+sha,observation=reference,
                    worker_sha256=identity()['worker_sha256'],
                    observation_sha256=hashlib.sha256((folder/'inspection/stdout.json').read_bytes()).hexdigest()))
            return response
        except Exception:
            response['cause']='adapter_infrastructure_failure'
            return response
        finally:
            # Host paths, raw exceptions, containment records and task data are
            # never included in this public reply. Full receipts stay operator-side.
            write_json(folder/'response.json',response)
            write_json(folder/'feedback.json',boundary_feedback.compact(response))
            tool_observation(folder,'boundary-tool',PROFILE['version'],started=observed_start,elapsed_seconds=time.monotonic()-observed_clock)
            write_json(self.output/'usage.json',dict(attempted_calls=self.calls,
                artifact_snapshots=sum((p/'model.xml').exists() for p in self.output.glob('call-*')),
                started_inspections=sum((p/'inspection').exists() for p in self.output.glob('call-*')),
                maximum_calls=PROFILE['max_calls']))


class AttachedSession:
    """Small Unix-socket bridge inside one existing contained builder."""
    def __init__(self, container_id, output, events):
        from builder.run import docker,verify_container
        from builder.openmc_python import IMAGE_ID
        info=json.loads(docker('inspect',container_id))[0]
        if info['Id']!=container_id or not info['State']['Running']:
            raise ValueError('Boundary adapter requires the current running builder container')
        verify_container(info,IMAGE_ID)
        self.session=Session(output,dict(container_id=container_id,image_id=info['Image']))
        write_json(self.session.output/'container.json',info)
        self.events=events;self.process=None;self.reader=None
        stage="import sys; from pathlib import Path; p=Path('/work/inspect_boundaries.py'); p.write_bytes(sys.stdin.buffer.read()); p.chmod(0o444)"
        value=bounded(['docker','exec','-i',container_id,'python3','-I','-B','-c',stage],
                      timeout=PROFILE['staging_seconds'],data=CLIENT.read_bytes())
        write_json(self.session.output/'client-staging.json',{k:value[k] for k in ('exit_code','stop_reason')})
        if value['exit_code']!=0 or value['stop_reason']:raise RuntimeError('Boundary client staging failed')
        stage="import sys; from pathlib import Path; p=Path('/work/boundary_feedback.py'); p.write_bytes(sys.stdin.buffer.read()); p.chmod(0o444)"
        value=bounded(['docker','exec','-i',container_id,'python3','-I','-B','-c',stage],
                      timeout=PROFILE['staging_seconds'],data=FEEDBACK.read_bytes())
        write_json(self.session.output/'feedback-staging.json',{k:value[k] for k in ('exit_code','stop_reason')})
        if value['exit_code']!=0 or value['stop_reason']:raise RuntimeError('Boundary feedback staging failed')
        (self.session.output/'client.py').write_bytes(CLIENT.read_bytes())
        (self.session.output/'bridge.py').write_bytes(BRIDGE.read_bytes())
        self.process=subprocess.Popen(['docker','exec','-i',container_id,'python3','-I','-B','-c',BRIDGE.read_text()],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        ready=queue.Queue()
        def pump():
            first=True
            try:
                while True:
                    line=self.process.stdout.readline(PROFILE['response_bytes']+1)
                    if not line:break
                    if len(line)>PROFILE['response_bytes']:raise ValueError('Oversized bridge frame')
                    frame=json.loads(line)
                    if first:ready.put(frame);first=False
                    else:events.put(dict(type='boundary_tool_request',frame=frame))
            except Exception:
                events.put(dict(type='boundary_tool_error'))
        self.reader=threading.Thread(target=pump,daemon=True);self.reader.start()
        try:
            if ready.get(timeout=PROFILE['bridge_start_seconds'])!={'type':'boundary_ready'}:
                raise RuntimeError('Boundary bridge did not become ready')
        except Exception:
            self.close();raise

    def handle(self, frame, remaining_seconds):
        if not isinstance(frame,dict) or set(frame)!={'id','request'} or frame['id']!=self.session.calls+1:
            raise ValueError('Invalid boundary tool sequence')
        reply=self.session.inspect_boundaries(frame['request'],remaining_seconds=remaining_seconds)
        raw=json.dumps(dict(id=frame['id'],response=reply),allow_nan=False).encode()+b'\n'
        if len(raw)>PROFILE['response_bytes']:raise ValueError('Boundary response byte limit')
        self.process.stdin.write(raw);self.process.stdin.flush()
        if reply['cause']=='inspection_cleanup_uncertain':
            raise RuntimeError('Boundary inspector cleanup uncertain; stop the builder session')

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
            for pipe in (self.process.stdin,self.process.stdout):pipe.close()
        if self.reader is not None:self.reader.join(timeout=5)
        write_json(self.session.output/'bridge-cleanup.json',dict(host_bridge_closed=True,
            owner_container_removal_required=True,attempted_calls=self.session.calls))
