"""Explicit campaign membership and operational progress, never scientific verdicts."""
from collections import Counter
import hashlib
import json
import re
from pathlib import Path

from dashboard.projection import Evidence, confined


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def selection(runs=(), manifest=None):
    """Only operator-selected manifests may introduce campaign directories."""
    from dashboard.campaign import selected_roots
    roots = list(runs or [])
    studies = []
    if manifest:
        path = Path(manifest).resolve()
        value = Evidence(path.parent).json(path.name)
        if not value:
            raise ValueError('Unreadable dashboard selection')
        if value.get('format') in ('dashboard-live-campaign-v1', 'dashboard-live-campaign-v2'):
            studies = [path]
        else:
            for key in ('runs', 'campaigns'):
                entries = value.get(key, [])
                if not isinstance(entries, list) or any(not isinstance(p, str) or not p for p in entries):
                    raise ValueError('Invalid dashboard selection paths')
            roots.extend(path.parent/p for p in value.get('runs', []))
            studies = [path.parent/p for p in value.get('campaigns', [])]
    campaigns, members = read_studies(studies)
    roots.extend(Path(p) for p in members)
    return selected_roots(roots), [Path(p).resolve() for p in studies]


def read_studies(paths):
    campaigns, members, seen, all_executions = [], {}, set(), set()
    for path in paths:
        path = Path(path)
        if path.is_symlink():
            raise ValueError('Linked campaign manifest')
        path = path.resolve()
        evidence = Evidence(path.parent)
        manifest = evidence.json(path.name)
        if not manifest or manifest.get('format') not in ('dashboard-live-campaign-v1', 'dashboard-live-campaign-v2'):
            raise ValueError('Unsupported campaign manifest')
        cid = manifest.get('campaign_id') or 'retained-'+identity(manifest)
        if not isinstance(cid, str) or not cid or cid in seen:
            raise ValueError('Duplicate or invalid campaign identity')
        seen.add(cid)
        rows = manifest.get('rows')
        if not isinstance(rows, list) or not rows or type(manifest.get('sessions')) is not int or len(rows) != manifest['sessions'] or len(rows)>1000:
            raise ValueError('Inconsistent expected campaign inventory')
        if not isinstance(manifest.get('name', path.parent.name), str):
            raise ValueError('Invalid campaign name')
        progress = evidence.json('progress.json') or {}
        launch = evidence.json('launch.json') or {}
        if evidence.raw('launch.json') is not None and not launch:
            raise ValueError('Unreadable campaign launch receipt')
        if launch and launch.get('manifest_sha256') != hashlib.sha256(evidence.raw(path.name)).hexdigest():
            raise ValueError('Launched campaign manifest changed')
        if manifest.get('reference') is not None and not isinstance(manifest['reference'],str):
            raise ValueError('Invalid declared reference scope')
        scope = {'public_demo_only':'public_demo', 'private_frozen_suite':'private'}.get(manifest.get('reference'))
        for row in rows:
            if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k] for k in ('id','case','model','arm','path')):
                raise ValueError('Invalid campaign row')
            if Path(row['case']).name != row['case'] or row['case'] in ('.','..') or type(row.get('repeat')) is not int or row['repeat']<1:
                raise ValueError('Invalid task or repeat identity')
            if manifest['format']=='dashboard-live-campaign-v2' and (
                    not isinstance(manifest.get('campaign_id'),str) or not manifest['campaign_id'] or
                    not isinstance(row.get('run_id'),str) or not row['run_id'] or
                    not isinstance(row.get('plan_sha256'),str) or not re.fullmatch(r'[0-9a-f]{64}',row['plan_sha256'])):
                raise ValueError('Missing explicit v2 campaign/run identity or plan binding')
            eid = row.get('run_id') or cid+':'+str(row.get('id'))
            if not isinstance(eid, str) or not eid or eid in all_executions:
                raise ValueError('Duplicate or invalid execution identity')
            all_executions.add(eid)
            raw = Path(row['path'])
            folder = raw if raw.is_absolute() else path.parent/raw
            # Campaign membership cannot expand access outside the selected campaign.
            if folder.is_symlink() or not folder.resolve().is_relative_to(path.parent):
                raise ValueError('Campaign execution outside selected directory')
            confined(path.parent, folder.relative_to(path.parent))
            folder = folder.resolve()
            if str(folder) in members:
                raise ValueError('Execution directory assigned to multiple campaigns')
            members[str(folder)] = dict(campaign_id=cid, execution_id=eid,
                campaign_name=manifest.get('name', path.parent.name), case=row['case'],
                model=row['model'], configuration=row['arm'], repeat=row['repeat'],
                plan_sha256=row.get('plan_sha256'), reference_scope=scope)
        campaigns.append(dict(id=cid, name=manifest.get('name', path.parent.name),
            identity_source='recorded' if manifest.get('campaign_id') else 'retained_manifest_digest',
            expected=len(rows), state=progress.get('state', 'unknown'), error=progress.get('error'),
            reference_scope=scope, kind=manifest.get('kind'), warnings=evidence.warnings))
    return campaigns, members


def decorate(records, roots, paths):
    campaigns, members = read_studies(paths)
    for record in records:
        root = Path(roots[record['run']]).resolve()
        member = members.get(str(root))
        record.update(campaign_id=None, campaign_name=None, repeat=None,
            observed_reference_scope=record['context']['reference_scope'],
            execution_id=record.get('execution_id') or 'legacy-location-'+identity([str(root), record['case']]),
            identity_source='recorded' if record.get('execution_id') else 'legacy_location',
            declared_reference_scope=None, membership_conflicts=[])
        if member:
            conflicts = [k for k in ('case', 'configuration') if record[k] != member[k]]
            if record['identity_source'] == 'recorded' and record['execution_id'] != member['execution_id']:
                conflicts.append('execution_id')
            if record['context']['model'] != member['model']:
                conflicts.append('model')
            raw = Evidence(root).raw('plan.json')
            if member['plan_sha256'] and (raw is None or hashlib.sha256(raw).hexdigest() != member['plan_sha256']):
                conflicts.append('plan_sha256')
            observed = record['context']['reference_scope']
            if observed and member['reference_scope'] and observed != member['reference_scope']:
                conflicts.append('reference_scope')
            record.update(campaign_id=member['campaign_id'], campaign_name=member['campaign_name'],
                execution_id=member['execution_id'], identity_source='campaign_manifest', repeat=member['repeat'],
                declared_reference_scope=member['reference_scope'], membership_conflicts=conflicts)
            if observed is None:
                record['context']['reference_scope'] = member['reference_scope']
            # Stable planned groups. Observed context conflicts still block comparisons.
            record['cohort'] = identity([member['campaign_id'], record['context']['model']])[:16]
        if not record.get('plan_available'):
            record['lifecycle'] = 'missing'
    identities = Counter(r['execution_id'] for r in records)
    if any(count>1 for count in identities.values()):
        raise ValueError('Duplicate execution identity; copied evidence cannot be counted twice')
    for study in campaigns:
        rows = [r for r in records if r['campaign_id'] == study['id']]
        counts = Counter(r['lifecycle'] for r in rows)
        study.update(counts=dict(counts), loaded=len(rows),
            conflicts=sum(bool(r['membership_conflicts']) for r in rows),
            missing=max(0, study['expected']-len(rows))+counts['missing'])
    return campaigns
