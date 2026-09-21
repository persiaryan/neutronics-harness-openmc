"""Case-specific fidelity assessment from independently observed XML semantics."""
from evaluation.scientific.records import close
from evaluation.benchmark_suite.suite_cases import SPECS, probes, expected, check_materials


def settings_checks(case, root, sampling):
    spec=SPECS[case]; s=root.find('settings'); checks=[]; unsupported=[]
    def check(name, actual, target):
        if isinstance(target,list):
            ok=isinstance(actual,list) and len(actual)==len(target) and all(close(a,b) for a,b in zip(actual,target))
        elif isinstance(target,(float,int)) and not isinstance(target,bool):
            ok=actual is not None and close(actual,target)
        else: ok=actual==target
        checks.append(dict(field=name,actual=actual,expected=target,passed=ok))
    def numbers(text): return [float(v) for v in text.split()] if text else None
    for name,default,target in [('run_mode','eigenvalue','eigenvalue'),('energy_mode','continuous-energy','continuous-energy'),
                                ('temperature_method','nearest','nearest')]: check(name,s.findtext(name,default),target)
    for name,default in [('particles','0'),('batches','0'),('inactive','0'),('generations_per_batch','1'),('seed','1')]:
        check(name,float(s.findtext(name,default)),sampling[name])
    check('temperature_tolerance',float(s.findtext('temperature_tolerance','10')),1.)
    check('temperature_multipole',s.findtext('temperature_multipole','false') in ('true','1'),False)
    allowed={'run_mode','energy_mode','particles','batches','inactive','generations_per_batch','seed','source',
             'temperature_default','temperature_method','temperature_tolerance','temperature_multipole','temperature_range',
             'mesh','entropy_mesh','output','state_point','source_point','verbosity'}
    unsupported.extend(c.tag for c in s if c.tag not in allowed)
    sources=s.findall('source');check('source_count',len(sources),1)
    if len(sources)==1:
        source=sources[0]; space=source.find('space');kind=space.get('type') if space is not None else None
        check('source_type',source.get('type','independent'),'independent')
        check('source_particle',source.get('particle','neutron'),'neutron')
        check('source_space',kind in ('box','fission') if sampling['source']=='uniform' else kind=='point',True)
        check('source_parameters',None if space is None else numbers(space.findtext('parameters')),
              spec['active'] if sampling['source']=='uniform' else spec['point'])
        check('source_fissionable',kind=='fission' or source.findtext('constraints/fissionable','false') in ('true','1'),True)
        check('source_rejection',source.findtext('constraints/rejection_strategy','resample'),'resample')
        angle,energy=source.find('angle'),source.find('energy')
        check('source_angle','isotropic' if angle is None else angle.get('type'),'isotropic')
        check('source_energy','watt' if energy is None else energy.get('type'),'watt')
        check('source_watt',[988000.,2.249e-6] if energy is None else numbers(energy.get('parameters')),[988000.,2.249e-6])
        unsupported.extend('source/'+c.tag for c in source if c.tag not in {'space','angle','energy','constraints','strength'})
        constraints=source.find('constraints')
        if constraints is not None:
            unsupported.extend('constraints/'+c.tag for c in constraints if c.tag not in {'fissionable','rejection_strategy'})
    meshes=[m for m in s.findall('mesh') if m.get('id')==s.findtext('entropy_mesh')]
    check('entropy_mesh_count',len(meshes),1)
    if len(meshes)==1:
        m=meshes[0];check('entropy_mesh_type',m.get('type','regular'),'regular')
        check('entropy_dimensions',numbers(m.findtext('dimension')),spec['mesh'])
        check('entropy_lower_left',numbers(m.findtext('lower_left')),spec['active'][:3])
        upper=numbers(m.findtext('upper_right'))
        if upper is None and m.find('width') is not None:
            low,width,dim=[numbers(m.findtext(t)) for t in ('lower_left','width','dimension')]
            if low and width and dim: upper=[a+b*c for a,b,c in zip(low,width,dim)]
        check('entropy_upper_right',upper,spec['active'][3:])
    statepoints=numbers(s.findtext('state_point/batches'))
    check('final_statepoint',statepoints is None or sampling['batches'] in statepoints,True)
    return dict(status='discrepancy' if any(not c['passed'] for c in checks) else 'inconclusive' if unsupported else 'passed_checks',
                checks=checks,unassessed_options=unsupported)


def assess(case, root, observation, sampling, *, boundary_result):
    settings=settings_checks(case,root,sampling)
    if observation.get('status')!='inspected' or observation.get('cleanup_confirmed') is not True:
        return dict(status='inconclusive',settings=settings)
    roles,material_checks=check_materials(case,observation['materials'])
    points,groups=probes(case)
    if len(points)!=len(observation['observations']): raise ValueError('Observation count mismatch')
    counts={};failures=[];temp_failures=0;invalid_geometry=0
    for index,(p,group,(state,leaves)) in enumerate(zip(points,groups,observation['observations'])):
        target=expected(case,p)
        actual=('outside' if state=='outside' else ('void' if leaves[0][0] is None else roles.get(str(leaves[0][0]),'unknown'))
                if state=='ok' and len(leaves)==1 else state)
        count=counts.setdefault(group,dict(probes=0,failures=0));count['probes']+=1;count['failures']+=actual!=target
        invalid_geometry+=state in ('overlap','missing','gap','lost') or (state=='outside' and target!='outside')
        thermal=all(close(t,293.6) for m,t in leaves if m is not None);temp_failures+=not thermal
        if (actual!=target or not thermal) and len(failures)<20:
            failures.append(dict(probe=index,point=p,expected=target,actual=actual,state=state))
    result=dict(materials=dict(status='passed_checks' if all(c['passed'] for c in material_checks) and not temp_failures else 'discrepancy',
                               checks=material_checks,temperature_failures=temp_failures),
                geometry=dict(status='passed_checks' if all(g['failures']==0 for g in counts.values()) else 'discrepancy',
                              probes=len(points),groups=counts,invalid_geometry=invalid_geometry,first_discrepancies=failures),
                boundaries=boundary_result,settings=settings)
    states={v['status'] for v in result.values()}
    result['status']='discrepancy' if 'discrepancy' in states else 'inconclusive' if 'inconclusive' in states else 'passed_checks'
    result['coverage']='Finite all-matching-cell probes and reachable boundary inventory, not exhaustive proof of CSG correctness.'
    return result
