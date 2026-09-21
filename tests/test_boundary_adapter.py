"""Adapter access, bounded failures and explicit condition routing, locally only."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from builder import boundary_tool,run
from evaluator.profiles import FACTORY_PROFILE,BOUNDARY_PROTOCOL
from evaluator.contracts import FACTORY
from prompts.prepare import prepare


class AdapterTests(unittest.TestCase):
    def test_host_paths_artifact_ids_and_other_session_requests_are_not_interfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i,request in enumerate([dict(tool='inspect_boundaries',path='/private/reference/model.xml'),
                dict(tool='inspect_boundaries',artifact_id='other-session:artifact'),
                dict(tool='inspect_boundaries',xml='<model/>',session_id='other-session')]):
                session=boundary_tool.Session(Path(tmp)/str(i),dict(container_id='local test double'))
                with patch.object(boundary_tool.boundaries,'observe') as observe:
                    response=session.inspect_boundaries(request,remaining_seconds=600)
                observe.assert_not_called();self.assertEqual(response['cause'],'invalid_request')
                self.assertNotIn('/private',json.dumps(response));self.assertIsNone(response['observations'])

    def test_budget_and_malformed_artifact_are_explicit_indeterminate(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=boundary_tool.Session(Path(tmp)/'session',{})
            with patch.object(boundary_tool.boundaries,'observe') as observe:
                a=session.inspect_boundaries(dict(tool='inspect_boundaries',xml='<model/>'),remaining_seconds=600)
                b=session.inspect_boundaries(dict(tool='inspect_boundaries',xml='<model/>'),remaining_seconds=10)
                c=session.inspect_boundaries(dict(tool='inspect_boundaries',xml='<model/>'),remaining_seconds=600)
            observe.assert_not_called()
            self.assertEqual([r['cause'] for r in (a,b,c)],['artifact_not_admitted','insufficient_remaining_session_budget','tool_call_budget_exhausted'])
            self.assertTrue(all(r['status']=='indeterminate' for r in (a,b,c)))
            with self.assertRaisesRegex(ValueError,'already exhausted'):
                session.inspect_boundaries({},remaining_seconds=600)
            self.assertEqual(len(list(session.output.glob('call-*'))),3)

    def test_extra_large_artifact_rejected_before_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=boundary_tool.Session(Path(tmp)/'session',{})
            with patch.object(boundary_tool.boundaries,'observe') as observe:
                value=session.inspect_boundaries(dict(tool='inspect_boundaries',xml='x'*500001),remaining_seconds=600)
            observe.assert_not_called();self.assertEqual(value['cause'],'artifact_byte_limit')


    def test_read_only_adapter_failure_does_not_leak_host_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=boundary_tool.Session(Path(tmp)/'session',{})
            with patch.object(boundary_tool,'admit'),patch.object(boundary_tool.boundaries,'observe',side_effect=OSError('/private/reference/secrets')):
                value=session.inspect_boundaries(dict(tool='inspect_boundaries',xml='<model/>'),remaining_seconds=600)
            self.assertEqual(value['cause'],'adapter_infrastructure_failure')
            self.assertNotIn('/private',json.dumps(value))


    def test_nonuse_is_explicit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=boundary_tool.Session(Path(tmp)/'session',{})
            self.assertEqual(json.loads((session.output/'usage.json').read_bytes())['attempted_calls'],0)
