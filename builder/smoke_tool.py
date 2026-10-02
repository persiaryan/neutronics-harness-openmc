"""Second bounded command over the existing candidate-local stdio/socket mechanism."""
import json
from pathlib import Path
import queue
import subprocess
import threading
import uuid

from builder import boundary_tool,smoke_feedback
import time
from observability import now, tool_observation
from evaluator import smoke
from evaluator.run import bounded,write_json,digest

PROFILE=smoke.PROFILE
FEEDBACK=Path(smoke_feedback.__file__)
# Reuse the qualified path reader, exclusive report publisher and byte-only pipe.
# Only command/module/socket names differ; no alternative IPC implementation.
CLIENT=boundary_tool.CLIENT.read_text().replace('boundary_feedback','smoke_feedback').replace(
    'inspect_boundaries','smoke_openmc').replace('inspect-boundaries.sock','smoke-openmc.sock')
BRIDGE=boundary_tool.BRIDGE.read_text().replace('inspect-boundaries.sock','smoke-openmc.sock').replace(
    'boundary_ready','smoke_ready')


def identity():
    return dict(version='candidate-smoke-tool-v1',profile=PROFILE,feedback_format=smoke_feedback.VERSION,
        sources={str(p.name):digest(p.read_bytes()) for p in (Path(__file__),Path(smoke.__file__),
                 Path(smoke.transport.__file__),FEEDBACK)},client_sha256=digest(CLIENT.encode()),
        bridge_sha256=digest(BRIDGE.encode()),image_id=smoke.transport.IMAGE,
        reference_access=False,scoring=False,automatic_repair=False)


class Session:
    def __init__(self,output,owner,index):
        self.output=Path(output);self.output.mkdir(parents=True,exist_ok=False)
        self.owner=owner;self.index=Path(index);self.id=uuid.uuid4().hex;self.calls=0;self.cleanup_confirmed=True
        write_json(self.output/'session.json',dict(session_id=self.id,owner=owner,**identity()))
        for path in (Path(__file__),Path(smoke.__file__),Path(smoke.transport.__file__),FEEDBACK):
            (self.output/path.name).write_bytes(path.read_bytes())
        self.usage()

    def usage(self):
        write_json(self.output/'usage.json',dict(attempted_calls=self.calls,maximum_calls=PROFILE['max_calls'],
            native_attempts=sum((p/'execution/transport/openmc-process.json').exists() for p in self.output.glob('call-*'))))

    def invoke(self,request,*,remaining_seconds):
        if self.calls>=PROFILE['max_calls']+1:raise ValueError('Smoke request budget exhausted')
        self.calls+=1;folder=self.output/f'call-{self.calls:02d}';folder.mkdir()
        observed_start, observed_clock = now(), time.monotonic()
        write_json(folder/'request.json',request)
        response=dict(format='candidate-smoke-result-v1',status='not_started',cause=None,native_outcome='not_started',
            evidence_reference=f'smoke-run:{self.id}:{self.calls}',profile=PROFILE,
            logs={},processes={},cleanup_confirmed=True,task_conformity='not_evaluated',
            reference_access=False,scoring=False,automatic_repair=False)
        try:
            if self.calls>PROFILE['max_calls']:
                response['cause']='tool_call_budget_exhausted';return response
            if remaining_seconds<PROFILE['minimum_session_seconds_to_start']:
                response['cause']='insufficient_remaining_session_budget';return response
            if not isinstance(request,dict) or set(request)!={'tool','xml'} or request['tool']!='smoke_openmc' or not isinstance(request['xml'],str):
                response['cause']='invalid_request';return response
            xml=request['xml'].encode()
            if not 0<len(xml)<=PROFILE['max_xml_bytes']:
                response['cause']='artifact_byte_limit';return response
            response['working_xml_sha256']=digest(xml)
            response.update(smoke.execute(xml,folder/'execution',index=self.index))
            return response
        except (ValueError,TypeError) as exc:
            # These are admission diagnostics, not controller paths or credentials.
            response.update(cause='smoke_input_not_admitted',input_error=str(exc)[:500])
            return response
        except Exception:
            response.update(status='indeterminate',cause='smoke_controller_failure',cleanup_confirmed=False)
            return response
        finally:
            self.cleanup_confirmed=self.cleanup_confirmed and response.get('cleanup_confirmed') is True
            write_json(folder/'response.json',response)
            write_json(folder/'feedback.json',smoke_feedback.compact(response));self.usage()
            tool_observation(folder,'smoke-tool','candidate-smoke-tool-v1',started=observed_start,elapsed_seconds=time.monotonic()-observed_clock)


class AttachedSession:
    """Attach the same byte bridge to one verified owner, with a separate socket."""
    def __init__(self,container_id,output,events,index):
        from builder.run import docker,verify_container
        from builder.openmc_python import IMAGE_ID
        info=json.loads(docker('inspect',container_id))[0]
        if info['Id']!=container_id or not info['State']['Running']:raise ValueError('Smoke owner is not running')
        verify_container(info,IMAGE_ID)
        self.session=Session(output,dict(container_id=container_id,image_id=info['Image']),index)
        self.process=None;self.reader=None
        write_json(self.session.output/'container.json',info)
        for name,raw in [('smoke_openmc.py',CLIENT.encode()),('smoke_feedback.py',FEEDBACK.read_bytes())]:
            stage="import sys; from pathlib import Path; p=Path('/work/"+name+"'); p.write_bytes(sys.stdin.buffer.read()); p.chmod(0o444)"
            value=bounded(['docker','exec','-i',container_id,'python3','-I','-B','-c',stage],timeout=30,data=raw)
            write_json(self.session.output/(name+'-staging.json'),{k:value[k] for k in ('exit_code','stop_reason')})
            if value['exit_code']!=0 or value['stop_reason']:raise RuntimeError('Smoke client staging failed')
        (self.session.output/'client.py').write_text(CLIENT);(self.session.output/'bridge.py').write_text(BRIDGE)
        self.process=subprocess.Popen(['docker','exec','-i',container_id,'python3','-I','-B','-c',BRIDGE],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        ready=queue.Queue()
        def pump():
            first=True
            try:
                while True:
                    line=self.process.stdout.readline(1800001)
                    if not line:break
                    if len(line)>1800000:raise ValueError('Oversized smoke bridge frame')
                    frame=json.loads(line)
                    if first:ready.put(frame);first=False
                    else:events.put(dict(type='smoke_tool_request',frame=frame))
            except Exception:events.put(dict(type='smoke_tool_error'))
        self.reader=threading.Thread(target=pump,daemon=True);self.reader.start()
        try:
            if ready.get(timeout=10)!={'type':'smoke_ready'}:raise RuntimeError('Smoke bridge did not become ready')
        except Exception:
            self.close();raise

    def handle(self,frame,remaining_seconds):
        if not isinstance(frame,dict) or set(frame)!={'id','request'} or frame['id']!=self.session.calls+1:
            raise ValueError('Invalid smoke request sequence')
        reply=self.session.invoke(frame['request'],remaining_seconds=remaining_seconds)
        raw=json.dumps(dict(id=frame['id'],response=reply),allow_nan=False).encode()+b'\n'
        if len(raw)>1800000:raise ValueError('Smoke response byte limit')
        self.process.stdin.write(raw);self.process.stdin.flush()
        if not reply.get('cleanup_confirmed'):raise RuntimeError('Smoke cleanup uncertain; stop builder')

    # Identical bridge lifecycle and owner-removal contract.
    close=boundary_tool.AttachedSession.close
