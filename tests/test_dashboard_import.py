"""A synthetic sealed 150-slot archive; no real conversations, data or native runs."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from dashboard.import_study import import_study, sha
from tests import test_dashboard_campaign as fixtures


class ImportTest(unittest.TestCase):
    def archive(self, root):
        source=root/'source';source.mkdir()
        fixture=fixtures.CampaignTest();fixture.root=root/'fixtures';fixture.root.mkdir()
        fixture.roots=[];fixture.rubric=sha(Path('evaluation/benchmark_suite/scoring.json'))
        base=source/'evidence/abc-temperature-amendment-v1'
        rows=[];order=0
        for model,counts in [('gpt-5.6-luna',[18,17,14]),('gpt-5.6-sol',[23,25,21])]:
            for arm,passes in zip('ABC',counts):
                for repeat in range(1,26):
                    order+=1;ident=f'{order:03d}-synthetic';case='task-one'
                    folder,report,_=fixture.run_fixture(config=arm,model=model,result='pass' if repeat<=passes else 'fail')
                    original=(source/'evidence/abc-request16-development-v1/study-01' if order<=38 else base/'study-01')/'trials'/ident
                    original.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(folder),original)
                    task=original/'runs'/case
                    (task/'candidate.py').write_text('raise RuntimeError("Archived candidate must never execute")\n')
                    (task/'builder/unused.h5').write_bytes(b'Native binary is not imported')
                    selected=task/'assessment/report.json'
                    category='scored'
                    if order==150:
                        shutil.rmtree(selected.parent);selected=None;category='provider_or_stream_incident'
                        fixture.write(task/'builder/result.json',{'status':'stopped'})
                    elif order<=38:
                        destination=source/'evidence/selected-v7'/ident
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        shutil.move(str(selected.parent),destination)
                        (destination/'review.json').rename(destination/'verification.json')
                        selected=destination/'report.json'
                    rows.append(dict(id=ident,case=case,order=order,category=category,
                        diagnostic_score=report['diagnostic_score']['score'] if selected else None,
                        assessment_evidence=str(selected.relative_to(source)) if selected else None))
        analysis=base/'analysis-02/analysis.json';fixture.write(analysis,dict(complete=True,trials=rows))
        inventory={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
        seal=base/'closeout-02/seal.json';fixture.write(seal,{'inventory':inventory})
        fixture.write(seal.with_name('verification.json'),dict(seal_sha256=sha(seal),analysis_files={str(analysis.relative_to(source)):sha(analysis)}))
        locations=root/'locations.json';fixture.write(locations,dict(source_root=str(source),records=[{'id':r['id']} for r in rows]))
        return locations,source,seal

    def test_full_import_preserves_counts_review_aliases_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);locations,source,seal=self.archive(root)
            original=sha(seal)
            selected=import_study(locations,root/'imported')
            state=json.loads((selected.parent/'campaign-state.json').read_text())
            self.assertEqual(state['assignments'],150);self.assertEqual(len(state['cohorts']),2)
            for cohort in state['cohorts']:
                expected=[18,17,14] if cohort['context']['model']=='gpt-5.6-luna' else [23,25,21]
                self.assertEqual([cohort['groups'][a]['domains']['overall']['passed'] for a in 'ABC'],expected)
            self.assertEqual(sum(r['score'] is not None for r in state['records']),149)
            inherited=source/'evidence/selected-v7/001-synthetic/verification.json'
            self.assertEqual(inherited.read_bytes(),(selected.parent/'001-synthetic/runs/task-one/assessment/review.json').read_bytes())
            self.assertFalse(list(selected.parent.rglob('*.h5')))
            self.assertEqual(sha(seal),original)
            self.assertIn('must never execute',(selected.parent/'001-synthetic/runs/task-one/candidate.py').read_text())

    def test_changed_seal_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);locations,_,seal=self.archive(root)
            seal.write_text('{}')
            with self.assertRaisesRegex(ValueError,'seal changed'):import_study(locations,root/'imported')
            self.assertFalse((root/'imported').exists())


if __name__=='__main__':unittest.main()
