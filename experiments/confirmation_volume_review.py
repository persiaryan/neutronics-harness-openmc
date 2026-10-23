"""Independent analytic volumes versus retained uniform native point observations.

This is a bounded diagnostic, not a scored gate or exhaustive volume proof.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from builder.context import write_json
from evaluation.confirmation import cases
from evaluation.benchmark_suite.suite_cases import check_materials
from evaluation.scientific.records import inspection_record, require
from evaluation.scientific.inspection import WORKER
from evaluator.transport_input import accepted_export
from evaluator.profiles import PROFILE
from prompts.confirmation import TASKS


def analytic(case):
    i=TASKS.index(case);box=cases.OUTER[i]
    total=math.prod(box[a+3]-box[a] for a in range(3))
    result={}
    if i in (1,3,7,10,11):
        n={1:7,3:8,7:8,10:2,11:9}[i];height=1.26 if i==10 else 36
        fuel=n*math.pi*.4096**2*height
        result={'fuel_B':fuel,'void':n*math.pi*(.418**2-.4096**2)*height,
                'zirconium':n*math.pi*(.475**2-.418**2)*height}
        if i==3:result['fuel_A']=result['fuel_B']/2;result['fuel_B']/=2
        if i==7:result['zirconium']+=math.pi*(.56**2-.5**2)*36+74.6496
    elif i==0:result=dict(fuel_B=720.,void=57.6,zirconium=144.)
    elif i==2:
        result=dict(fuel_B=3*math.pi*(.55**2-.18**2)*32,
                    void=3*math.pi*(.56**2-.55**2)*32,
                    zirconium=3*math.pi*(.62**2-.56**2)*32)
    elif i==4:result=dict(mixture=1080.)
    elif i==5:result=dict(uranium_metal=2*math.pi*1.27**2)
    elif i==6:result=dict(mixture=1128.)
    elif i==8:result=dict(fuel_B=12.)
    elif i==9:result=dict(mixture=384*math.pi,void=39.36*math.pi)
    result['water']=total-sum(result.values())
    return total,result


def review(case, folder):
    folder=Path(folder)
    xml,_=accepted_export(folder/'export')
    observation=inspection_record(case,folder/'inspection',xml,WORKER.read_bytes(),image=PROFILE['export_image'])
    require(observation['status']=='inspected','Native observation missing')
    roles,_=check_materials(case,observation['materials'])
    _,groups=cases.probes(case);counts=Counter();n=0
    for group,(state,leaves) in zip(groups,observation['observations']):
        if group!='domain_samples':continue
        n+=1
        role=('void' if leaves[0][0] is None else roles.get(str(leaves[0][0]),'unknown')) if state=='ok' and len(leaves)==1 else state
        counts[role]+=1
    require(n==1400,'Unexpected diagnostic sample count')
    total,volumes=analytic(case)
    rows=[]
    for role,volume in volumes.items():
        estimate=total*counts[role]/n
        sigma=total*math.sqrt(volume/total*(1-volume/total)/n)
        rows.append(dict(role=role,analytic_cm3=volume,observed_points=counts[role],
                         finite_probe_estimate_cm3=estimate,expected_sampling_sigma_cm3=sigma))
    return dict(case=case,samples=n,rows=rows,unresolved_points=sum(v for k,v in counts.items() if k not in volumes),
        scope='Uniform finite native point observations compared with independent literal volume formulas; diagnostic only.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--controls',nargs='+',type=Path,required=True)
    p.add_argument('--cases',nargs='+',choices=TASKS,default=list(TASKS))
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    require(not a.output.exists(),'Use a fresh diagnostic output')
    rows=[]
    for case in a.cases:
        folders=[root/case/'correct' for root in a.controls if (root/case/'correct').exists()]
        require(len(folders)==1,'Missing/ambiguous correct fixture')
        rows.append(review(case,folders[0]))
    write_json(a.output,dict(format='confirmation-volume-diagnostic-v1',rows=rows,scientific_gate=False))
    print(json.dumps(dict(cases=len(rows),output=str(a.output))))


if __name__=='__main__':
    main()
