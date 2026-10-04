"""Prepare synthetic campaigns for browser QA. Never dispatches a model or solver."""
import argparse
import json
from pathlib import Path
import shutil

from tests.test_dashboard_collection import CollectionTest


def prepare(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    fixture=CollectionTest()
    fixture.root=output;fixture.roots=[]
    from experiments.dashboard_campaign import sha
    fixture.rubric=sha(Path('evaluation/benchmark_suite/scoring.json'))
    one,_,_=fixture.run_fixture(config='A')
    two,_,_=fixture.run_fixture(config='A',case='task-two',result='fail')
    pending,_,_=fixture.run_fixture(config='B');fixture.pending(pending)
    other,_,_=fixture.run_fixture(config='C',model='model-two')
    first,_=fixture.declare([one,two,pending,other],cid='campaign-one')
    second_root,_,_=fixture.run_fixture(config='A')
    second,_=fixture.declare([second_root],cid='campaign-two')
    legacy,_,_=fixture.run_fixture(config='A',case='legacy-one')
    extra,_,_=fixture.run_fixture(config='A',case='legacy-two')
    shutil.copytree(extra/'runs/legacy-two',legacy/'runs/legacy-two')
    plan=json.loads((legacy/'plan.json').read_text());plan['cases'].append('legacy-two')
    plan['prompts']['legacy-two']={'prompt_sha256':'legacy-two'}
    fixture.write(legacy/'plan.json',plan)
    for folder,case in [(one,'task-one'),(two,'task-two'),(legacy,'legacy-one'),(legacy,'legacy-two')]:
        path=folder/'inputs'/case/'prompt.txt';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('Synthetic task '+case+' <img src=x onerror="window.INJECTED=true">')
    fixture.write(output/'progress.json',dict(state='paused_on_incident',error='Synthetic resource stop'))
    # Public synthetic Luna/Sol comparison, safe to retain in QA screenshots.
    models=[]
    for model in ['gpt-5.6-luna','gpt-5.6-sol']:
        for config in ['A','B','C']:
            root,_,_=fixture.run_fixture(model=model,config=config,
                result='fail' if model=='gpt-5.6-luna' and config=='B' else 'pass')
            models.append(root)
    comparison,_=fixture.declare(models,cid='campaign-models')
    fixture.write(output/'selection.json',dict(campaigns=[first.name,second.name,comparison.name],runs=[legacy.name]))
    return output/'selection.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(prepare(parser.parse_args().output))
