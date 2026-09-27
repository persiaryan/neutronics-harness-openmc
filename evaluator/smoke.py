"""Bounded candidate-only transport diagnostics; no task, reference or scoring."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from evaluator import transport
from evaluator.inspect import parse_xml, inspect_model
from evaluator.run import digest, write_json
from evaluator.transport_input import transport_profile, read_regular

PROFILE = dict(id='candidate-smoke-v1', particles=1000, batches=8, inactive=2,
               generations_per_batch=1, seed=1, native_seconds=60,
               max_calls=2, minimum_session_seconds_to_start=180,
               max_xml_bytes=500000, log_bytes_per_stream=80000)


def prepare_xml(xml, index_name):
    """Explicit diagnostic copy, preserving physical inputs. Original bytes retained."""
    inspect_model(xml)
    root=parse_xml(xml);settings=root.find('settings');changes=[]
    replacements={k:str(PROFILE[k]) for k in ('particles','batches','inactive','generations_per_batch','seed')}
    # Output scheduling belongs to this short run, not the submitted model.
    replacements.update(state_point=None,source_point=None)
    for tag,value in replacements.items():
        nodes=settings.findall(tag)
        if len(nodes)>1:raise ValueError('Duplicate smoke setting: '+tag)
        before=[ET.tostring(n,encoding='unicode') for n in nodes]
        for node in nodes:settings.remove(node)
        if tag=='state_point':
            node=ET.SubElement(settings,tag);ET.SubElement(node,'batches').text=str(PROFILE['batches'])
        elif tag=='source_point':
            node=ET.SubElement(settings,tag);ET.SubElement(node,'write').text='false'
        else:ET.SubElement(settings,tag).text=value
        changes.append(dict(field='settings/'+tag,before_xml=before,
                            after_xml=ET.tostring(settings.find(tag),encoding='unicode')))
    materials=root.find('materials');nodes=materials.findall('cross_sections')
    if len(nodes)>1:raise ValueError('Duplicate nuclear-data index')
    before=[ET.tostring(n,encoding='unicode') for n in nodes]
    for node in nodes:materials.remove(node)
    ET.SubElement(materials,'cross_sections').text='/data/'+index_name
    changes.append(dict(field='materials/cross_sections',before_xml=before,after='/data/'+index_name,
                        reason='Explicit operator-selected smoke data; authoring placeholder is not nuclear data'))
    derived=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    transport_profile(derived,index_name)  # Same supported input restrictions as transport.
    return derived,changes


def execute(xml, output, *, index):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'working.xml').write_bytes(xml)
    derived,changes=prepare_xml(xml,Path(index).name)
    (output/'smoke.xml').write_bytes(derived)
    binding=dict(kind='candidate-session-smoke-v1',candidate_sha256=None,
                 working_xml_sha256=digest(xml),model_xml_sha256=digest(derived),
                 profile=PROFILE,overrides=changes,independent_final_export=False)
    write_json(output/'input.json',binding)
    result=transport.smoke_xml(derived,output/'transport',index=Path(index),provenance=binding,
                               wall_seconds=PROFILE['native_seconds'])
    return public_result(output,result)


def public_result(output,result):
    """Project externally recorded facts; diagnostic text never sets a grade."""
    output=Path(output);folder=output/'transport';binding=json.loads((output/'input.json').read_bytes())
    processes={};logs={}
    for phase in ('xml-load','openmc','statepoint'):
        path=folder/(phase+'-process.json')
        if path.exists():processes[phase]=json.loads(read_regular(path))
        for channel in ('stdout','stderr'):
            path=folder/(phase+'-'+channel+'.txt')
            if path.exists():
                raw=read_regular(path,limit=4_000_000);limit=PROFILE['log_bytes_per_stream']
                excerpt=raw if len(raw)<=limit else raw[:limit//2]+b'\n[omitted middle]\n'+raw[-limit//2:]
                logs[phase+'_'+channel]=dict(text=excerpt.decode('utf-8',errors='replace'),
                    bytes=len(raw),sha256=digest(raw),complete=len(raw)<=limit)
    native=processes.get('openmc')
    outcome='not_started'
    if native:
        outcome=('interrupted' if native['stop_reason'] else
                 'completed' if native['exit_code']==0 else 'failed')
    identities={}
    for name in ('data-before.json','runtime-identity.json'):
        if (folder/name).exists():identities[name]=digest(read_regular(folder/name,limit=32_000_000))
    return dict(format='candidate-smoke-result-v1',working_xml_sha256=binding['working_xml_sha256'],
        smoke_xml_sha256=binding['model_xml_sha256'],profile=PROFILE,overrides=binding['overrides'],
        openmc_version='0.15.3',image_id=transport.IMAGE,identities=identities,
        native_outcome=outcome,processes=processes,logs=logs,
        status=('completed' if result['status']=='calculated_unreviewed' else 'incomplete'),
        cause=result.get('reason') or (None if result['status']=='calculated_unreviewed' else 'transport_setup_or_validation_failed'),statepoint_validation=result.get('statepoint_validation'),
        cleanup_confirmed=result.get('cleanup_confirmed') is True,elapsed_seconds=result.get('elapsed_seconds'),
        coverage='Eight batches with reduced sampling; no convergence, geometry-validity or task-conformity claim',
        limitations=['A successful smoke run can miss defects.',
                     'A failed run does not by itself establish model-versus-infrastructure attribution.',
                     'Numerical smoke output is not final evaluation.'],
        task_conformity='not_evaluated',reference_access=False,scoring=False,automatic_repair=False)
