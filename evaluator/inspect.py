"""Small, independent XML envelope check. No candidate imports or OpenMC calls."""
import xml.etree.ElementTree as ET

MAX_XML = 8_000_000


def parse_xml(data):
    if len(data) > MAX_XML:
        raise ValueError('XML exceeds byte limit')
    text = data.decode('utf-8')
    if '\x00' in text:
        raise ValueError('Only UTF-8 XML without NUL bytes is supported')
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('DTD and entity declarations are not allowed')
    root = ET.fromstring(text)
    pending = [(root, 1)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > 100_000 or depth > 128:
            raise ValueError('XML exceeds structural limits')
        if not isinstance(node.tag, str) or node.tag.startswith('{'):
            raise ValueError('XML namespaces/includes are not supported')
        pending.extend((child, depth + 1) for child in node)
    return root


def inspect_model(data):
    root = parse_xml(data)
    if root.tag != 'model':
        raise ValueError('Expected combined model XML root')
    tags = [child.tag for child in root]
    if len(tags) != len(set(tags)) or set(tags) - {'materials', 'geometry', 'settings', 'tallies', 'plots'}:
        raise ValueError('Duplicate or unsupported model sections')
    if not {'materials', 'geometry', 'settings'} <= set(tags):
        raise ValueError('Missing required model sections')
    if not root.findall('materials/material') or not root.findall('geometry/cell'):
        raise ValueError('Empty materials or geometry section')
    return {'status': 'passed', 'scope': 'combined_xml_envelope_only',
            'sections': tags, 'material_count': len(root.findall('materials/material')),
            'cell_count': len(root.findall('geometry/cell')),
            'scientific_fidelity': 'not_checked', 'openmc_xml_load': 'not_run'}
