"""Native XML controls from operator fixtures. No transport and no model calls."""
import argparse
import json
from pathlib import Path

from builder.context import write_json
from evaluation.confirmation import cases, qualify, references
from evaluation.candidates import assessment
from evaluation.scientific.records import require
from prompts.confirmation import TASKS


def inputs(case, source):
    marker='    geometry=openmc.Geometry(cells)'
    require(source.count(marker)==1,'Control fixture geometry marker missing')
    domain=[cases.SPECS[case]['outer'][:3],cases.SPECS[case]['outer'][3:]]
    alias=(f'    shared=box({domain[0]!r},{domain[1]!r})\n'
           '    accumulator=shared\n    accumulator &= ~occupied[0]\n'
           '    add(domain&~shared,water)\n')
    controls=[('correct',source,None),
              ('equivalent_order',source.replace(marker,'    cells.reverse()\n'+marker),None),
              ('shared_mutation',source.replace(marker,alias+marker),('geometry','invalid_geometry'))]
    if case=='staggered_seven_pin_cluster':
        text=source.replace('occupied.append(-s3&height)','occupied.append(+s2&-s3&height)')
        controls.append(('annulus_instead_of_envelope',text,('geometry','invalid_geometry')))
    if case=='dual_temperature_pin_pair':
        controls.append(('wrong_temperature',source.replace('temp=600.','temp=293.6'),('materials','temperature_failures')))
        controls.append(('wrong_boundary',source.replace("('reflective', 'reflective', 'reflective')",
                            "('vacuum', 'reflective', 'reflective')"),('boundaries','score_check')))
    if case=='restricted_source_nine_pin':
        text=source.replace('space=openmc.stats.Box([-0.1, -0.1, -5],[0.1, 0.1, 5])',
                            'space=openmc.stats.Box([-1.95,-1.95,-18],[1.95,1.95,18])')
        controls.append(('wrong_source',text,('settings','source')))
    require(all(text!=source for _,text,expected in controls if expected is not None),'A mutation did not change the fixture')
    return controls


def run(sources, output, index, selected=TASKS):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report=dict(format='confirmation-native-controls-v1',provider_calls=0,neutron_transport=False,
                evaluator_identity=references.identity(),rows=[])
    sampling=dict(references.read(references.PROTOCOL)['sampling'],seed=1)
    for case in selected:
        source=Path(sources,case+'.py').read_text()
        for name,text,expected in inputs(case,source):
            folder=output/case/name;folder.mkdir(parents=True)
            (folder/'reference.py').write_text(text)
            try:
                try:
                    qualify.inspect(case,folder,text.encode(),index,sampling)
                except ValueError:
                    if not (folder/'fidelity.json').exists():raise
                fidelity=references.read(folder/'fidelity.json')
                checks=assessment.fidelity_checks(case,fidelity)
                if expected is None:
                    require(all(v is True for group in ('geometry','materials','physics_settings')
                                for v in checks[group].values()),'Correct/equivalent fixture rejected')
                else:
                    group,field=expected
                    if field in ('invalid_geometry','temperature_failures'):
                        require(fidelity[group][field]>0,'Introduced defect was missed')
                    elif field=='score_check':
                        require(any(v['verdict']=='nonconforming' for v in fidelity[group]['verdicts']),
                                'Wrong boundary was missed')
                    else:
                        selected_checks=[c['passed'] for c in fidelity['settings']['checks']
                                         if c['field'] in ('source_space','source_parameters')]
                        require(any(v is False for v in selected_checks),'Wrong source was missed')
                row=dict(case=case,control=name,status='passed',expected='accept' if expected is None else 'detect')
            except Exception as exc:
                row=dict(case=case,control=name,status='failed',reason=str(exc),error_type=type(exc).__name__)
            report['rows'].append(row)
            report['status']='passed' if all(r['status']=='passed' for r in report['rows']) else 'failed'
            write_json(output/'report.json',report)
            print(json.dumps(row),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('sources','output','data-index'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cases',nargs='+',choices=TASKS,default=list(TASKS))
    a=p.parse_args()
    return run(a.sources,a.output,a.data_index.resolve(strict=True),a.cases)


if __name__=='__main__':
    main()
