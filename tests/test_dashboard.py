"""Operator UI controls: missingness, artifact identity, isolation and partial live files."""
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from dashboard.projection import snapshot
from dashboard.server import make_server
from observability import record


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = Path('runs/reflective_pin_cell')
        self.write('plan.json', dict(cases=['reflective_pin_cell'], model='synthetic', budgets={'model_requests':8}))

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        return path

    def test_pending_is_not_zero_or_success(self):
        state = snapshot(self.root)
        self.assertIsNone(state['tasks'][0]['report'])
        self.assertIsNone(state['tasks'][0]['builder']['result'])
        self.assertEqual(state['tasks'][0]['convergence'], [])

    def test_existing_score_and_verdicts_are_preserved_without_grading(self):
        report = dict(case='reflective_pin_cell',status='stopped',diagnostic_score={'score':0,'strict_correct':False},
                      gates={'model_builds':{'passed':False}},checks={'geometry':{'domain':None}},
                      fidelity={'materials':{'checks':[{'field':'density','expected':10.4,'actual':9,'passed':False}]}})
        self.write(self.base/'assessment/report.json', report)
        self.write(self.base/'assessment/review.json',dict(evidence_status='contradictory',score=None))
        self.write(self.base/'candidate.py', "raise RuntimeError('DASHBOARD MUST NOT IMPORT THIS')\n")
        with patch('subprocess.Popen', side_effect=AssertionError('No execution permitted')):
            state = snapshot(self.root)
        t=state['tasks'][0]
        self.assertEqual(t['report'], report)
        self.assertEqual(t['report']['diagnostic_score']['score'], 0)
        self.assertIsNone(t['review']['score'])
        self.assertEqual(t['assertions'][0]['actual'],9)
        self.assertFalse(t['assertions'][0]['passed'])

    def test_partial_runtime_line_and_later_completion(self):
        p=self.write(self.base/'builder/events.jsonl', '{"type":"request","id":1}\n{"type":"stdout"')
        first=snapshot(self.root)
        self.assertEqual(len(first['tasks'][0]['builder']['timeline']),1)
        self.assertTrue(first['warnings'])
        p.write_text('{"type":"request","id":1}\n'+json.dumps({'type':'stdout','text':json.dumps({'type':'item.completed','item':{'type':'command_execution','command':'echo ok','exit_code':0,'aggregated_output':'ok'}})})+'\n')
        second=snapshot(self.root)
        self.assertEqual(len(second['tasks'][0]['builder']['timeline']),2)
        self.assertEqual(second['warnings'],[])

    def test_only_emitted_reasoning_summary_is_exposed(self):
        self.write(self.base/'builder/events.jsonl','{"type":"request","id":1}\n')
        event={'type':'response.completed','response':{'output':[
            {'type':'reasoning','encrypted_content':'PRIVATE_HIDDEN_SENTINEL','content':'HIDDEN_REASONING',
             'summary':[{'type':'summary_text','text':'Checking units.'}]},
            {'type':'message','content':[{'type':'output_text','text':'<script>evil()</script>'}]}]}}
        self.write(self.base/'builder/response-01.sse','data: '+json.dumps(event)+'\n\n')
        result=snapshot(self.root)
        raw=json.dumps(result)
        self.assertIn('Checking units.',raw)
        self.assertNotIn('PRIVATE_HIDDEN_SENTINEL',raw)
        self.assertNotIn('HIDDEN_REASONING',raw)
        self.assertIn('<script>',raw)  # Inert text; the UI must escape it.
        self.assertFalse(any('response-01.sse'==a['path'].split('/')[-1] for a in result['artifacts']))

    def test_xml_identity_and_diff_uses_working_not_smoke_copy(self):
        work='<model>original</model>'
        final='<model>changed</model>'
        self.write(self.base/'assessment/export/artifacts/model.xml',final)
        self.write(self.base/'assessment/report.json',{'final_model':{'sha256':hashlib.sha256(final.encode()).hexdigest()}})
        self.write(self.base/'builder/smoke-tool/call-01/feedback.json',{'working_xml_sha256':hashlib.sha256(work.encode()).hexdigest(),'smoke_xml_sha256':'diagnostic-copy'})
        self.write(self.base/'builder/smoke-tool/call-01/execution/working.xml',work)
        t=snapshot(self.root)['tasks'][0]
        self.assertFalse(t['identities'][0]['identical'])
        self.assertIn('-<model>original</model>',t['xml_diff'])
        self.assertIn('+<model>changed</model>',t['xml_diff'])

    def test_invalid_json_and_nonfinite_history_remain_visible(self):
        self.write('plan.json','[1,2]')
        self.write(self.base/'assessment/report.json','{"score":')
        self.write(self.base/'assessment/transport/artifacts/convergence.csv','generation,active,k_generation,entropy_bits\n1,True,NaN,2\n')
        state=snapshot(self.root)
        self.assertIsNone(state['tasks'][0]['report'])
        self.assertEqual(state['tasks'][0]['convergence'],[])
        self.assertGreaterEqual(len(state['warnings']),3)

    def test_symlink_artifact_is_not_served(self):
        outside=self.root/'secret.txt'; outside.write_text('secret')
        path=self.root/self.base/'candidate.py';path.parent.mkdir(parents=True);path.symlink_to(outside)
        state=snapshot(self.root)
        self.assertIsNone(state['tasks'][0]['candidate'])
        self.assertNotIn('secret',json.dumps(state))
        self.assertTrue(state['warnings'])

    def test_live_phase_journal_does_not_set_scientific_verdict(self):
        folder=self.root/self.base/'assessment';folder.mkdir(parents=True)
        record(folder,'transport','started')
        t=snapshot(self.root)['tasks'][0]
        self.assertEqual(t['phases'][0]['state'],'started')
        self.assertIsNone(t['report'])

    def test_feedback_projection_accepts_both_existing_evidence_path_shapes(self):
        self.write(self.base/'builder/result.json', {'status':'completed'})
        self.write(self.base/'builder/boundary-tool/call-01/feedback.json', {'inspection_status':'observed'})
        self.write(self.base/'builder/smoke-tool/call-01/feedback.json', {'status':'completed'})
        projection=dict(inspection_calls=[dict(evidence='boundary-tool/call-01/response.json',
            feedback_delivery=dict(status='complete',inspection_request_turn=2,delivered_in='request-03.json'))],
            smoke_calls=[dict(evidence='smoke-tool/call-01',request_turn=3,
                feedback_delivery=dict(status='complete',request='request-04.json'))])
        with patch('dashboard.projection.summarize', return_value=projection):
            tools=snapshot(self.root)['tasks'][0]['builder']['tools']
        self.assertEqual([t['tool'] for t in tools],['boundary-tool','smoke-tool'])
        self.assertTrue(all(t['projection']['feedback_delivery']['status']=='complete' for t in tools))

    def test_completed_export_is_visible_before_final_report(self):
        self.write(self.base/'assessment/export/result.json', {'status':'exported'})
        t=snapshot(self.root)['tasks'][0]
        self.assertEqual(t['phase_results']['export']['status'],'exported')
        self.assertIsNone(t['report'])

    def test_telemetry_failure_does_not_break_execution(self):
        with patch('pathlib.Path.open', side_effect=OSError('disk unavailable')):
            with self.assertWarns(RuntimeWarning):
                record(self.root,'export','started')

    def test_http_origin_paths_methods_and_plain_text(self):
        self.write(self.base/'candidate.py','<script>alert(1)</script>')
        self.write('auth.json',{'secret':'NOT_FOR_BROWSER'})
        server=make_server([self.root],port=0)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            def get(path,host=None,origin=None,method='GET'):
                c=http.client.HTTPConnection('127.0.0.1',server.server_port)
                headers={}
                if host:headers['Host']=host
                if origin:headers['Origin']=origin
                c.request(method,path,headers=headers);r=c.getresponse();body=r.read();result=(r.status,dict(r.getheaders()),body);c.close();return result
            status,headers,body=get('/')
            self.assertEqual(status,200)
            self.assertIn(b'<html lang="en">',body)
            self.assertIn(b'id="language-select"',body)
            self.assertEqual(get('/i18n.js')[0],200)
            self.assertIn(b'const I18N',get('/i18n.js')[2])
            self.assertEqual(get('/campaign.js')[0],200)
            status, _, body=get('/api/campaign')
            self.assertEqual(status,200)
            campaign=json.loads(body)
            self.assertEqual(campaign['assignments'],1)
            self.assertEqual(campaign['records'][0]['domains']['overall'],'unknown')
            self.assertEqual(get('/api/campaign',host='evil.test')[0],403)
            self.assertNotIn(b'NOT_FOR_BROWSER',body)
            self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
            self.assertEqual(get('/api/state',host='evil.test')[0],403)
            self.assertEqual(get('/api/state',origin='https://evil.test')[0],403)
            self.assertEqual(get('/api/state',method='POST')[0],405)
            for path in ['auth.json','../secret','/etc/passwd','runs/reflective_pin_cell/builder/request-01.json']:
                self.assertEqual(get('/api/artifact?path='+path)[0],404)
            status,headers,body=get('/api/artifact?path=runs/reflective_pin_cell/candidate.py')
            self.assertEqual(status,200)
            self.assertEqual(headers['Content-Type'],'text/plain; charset=utf-8')
            self.assertEqual(body,b'<script>alert(1)</script>')
            self.assertNotIn(b'NOT_FOR_BROWSER',get('/api/state')[2])
        finally:
            server.shutdown();server.server_close();worker.join()


if __name__ == '__main__':
    unittest.main()
