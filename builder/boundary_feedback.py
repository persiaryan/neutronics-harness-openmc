"""Bounded presentation of observations, without task requirements or grading.

This standard-library module is also staged beside the candidate command.
It projects existing records; it does not interpret CSG or certify conformity.
"""
import hashlib
import json

VERSION = 'candidate-boundary-feedback-v1'
MAX_BYTES = 16000  # ASCII JSON; headroom below the outer exec default (~40k chars).


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def full_reference(reply):
    raw = encode(reply)
    digest = hashlib.sha256(raw).hexdigest()
    return dict(path='boundary-report-' + digest + '.json', sha256=digest,
                bytes=len(raw), evidence_reference=reply.get('evidence_reference'))


def compact(reply):
    """Define complete *presentation*, distinct from complete scientific coverage."""
    obs = reply.get('observations') or {}
    surfaces = {s['ref']: s for s in obs.get('surfaces', [])}
    domain = obs.get('domain')
    unresolved = []
    faces = []
    if domain is None or domain.get('status') != 'established':
        unresolved.append(dict(obligation='root_domain_and_face_participation',
            cause=(domain or {}).get('cause') or reply.get('cause') or 'observation_unavailable'))
    for face in obs.get('faces', []):
        properties = []
        for ref in face.get('surface_refs', []):
            surface = surfaces.get(ref)
            if surface is None:
                unresolved.append(dict(obligation='effective_face_properties', face=face['ref'],
                                       cause='referenced_surface_unavailable', surface=ref))
                continue
            properties.append({k: surface.get(k) for k in
                ('ref', 'boundary_type', 'effective_albedo', 'albedo_applicable', 'limitations')})
        faces.append(dict(face, effective_properties=properties))
        for cause in face.get('limitations', []):
            unresolved.append(dict(obligation='face_observation', face=face['ref'], cause=cause))
    if domain and domain.get('status') == 'established':
        for axis in range(3):
            for side in ('lower', 'upper'):
                if not any(f.get('axis') == axis and f.get('side') == side for f in faces):
                    unresolved.append(dict(obligation='face_observation', axis=axis, side=side,
                        cause='face_observation_unavailable', observer_causes=obs.get('limitations', [])))
    # Keep every surface limitation, including those outside the reported faces.
    surface_limits = [dict(surface=s['ref'], limitations=s['limitations'])
                      for s in surfaces.values() if s.get('limitations')]
    value = dict(format=VERSION, feedback_complete=True, presentation_cause=None,
        inspection_status=reply.get('status'), inspection_cause=reply.get('cause'),
        artifact_sha256=reply.get('artifact_sha256'), observer_version=obs.get('observer_version'),
        openmc_version=obs.get('openmc_version'), domain=domain, faces=faces,
        unresolved_observation_obligations=unresolved, coverage=obs.get('coverage'),
        scope=reply.get('scope'), scope_limitations=reply.get('limitations', []),
        observation_limitations=obs.get('limitations', []), surface_limitations=surface_limits,
        task_conformity='not_evaluated', global_geometry_validity='not_evaluated',
        counts=dict(surfaces=len(surfaces), faces=len(faces)), full_result=full_reference(reply),
        full_only=['complete_surface_inventory', 'surface_geometry_and_xml_provenance', 'raw_evidence'])
    if len(encode(value)) <= MAX_BYTES:
        return value
    # Never trim an array or a limitation and still label the presentation complete.
    omitted = ['faces', 'unresolved_observation_obligations', 'coverage', 'scope_limitations',
               'observation_limitations', 'surface_limitations', 'domain_details']
    return dict(format=VERSION, feedback_complete=False, presentation_cause='feedback_byte_limit',
        byte_limit=MAX_BYTES, required_bytes=len(encode(value)), omitted_sections=omitted,
        inspection_status=reply.get('status'), inspection_cause=reply.get('cause'),
        artifact_sha256=reply.get('artifact_sha256'), observer_version=obs.get('observer_version'),
        openmc_version=obs.get('openmc_version'),
        domain={k: (domain or {}).get(k) for k in ('status', 'cause')},
        scope=reply.get('scope'), counts=value['counts'], full_result=value['full_result'],
        task_conformity='not_evaluated', global_geometry_validity='not_evaluated',
        limitations_and_unresolved_obligations='read_full_result_before_interpreting')
