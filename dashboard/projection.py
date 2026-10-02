"""Read bounded run evidence; never import candidates, launch tools or calculate scores."""
import csv
import difflib
import hashlib
import io
import json
import math
from pathlib import Path

from builder.relay import event_frame
from builder.trajectory import response_items, summarize
from dashboard.contracts import configuration_view, normalize_evaluation
from observation_contracts import catalog

MAX_FILE = 32_000_000
MAX_TEXT = 50_000


def confined(root, relative):
    root = Path(root).resolve()
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Path outside selected run')
    target = root
    for part in relative.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError('Symlink evidence is not served')
    if not target.resolve().is_relative_to(root):
        raise ValueError('Path outside selected run')
    return target


class Evidence:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.warnings = []
        self.artifacts = {}

    def raw(self, relative, *, register=False):
        relative = str(relative)
        try:
            path = confined(self.root, relative)
            if not path.exists():
                return None
            if not path.is_file() or path.stat().st_size > MAX_FILE:
                raise ValueError('Non-regular or oversized evidence')
            with path.open('rb') as stream:
                data = stream.read(MAX_FILE + 1)
            if len(data) > MAX_FILE:
                raise ValueError('Oversized evidence')
            if register:
                self.artifacts[relative] = dict(path=relative, bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest())
            return data
        except (OSError, ValueError) as exc:
            self.warnings.append(dict(path=relative, reason=str(exc)))
            return None

    def text(self, relative, *, register=True):
        data = self.raw(relative, register=register)
        return data.decode('utf-8', errors='replace') if data is not None else None

    def json(self, relative, *, register=False):
        raw = self.raw(relative, register=register)
        if raw is None:
            return None
        try:
            value = json.loads(raw, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
            if not isinstance(value, dict):
                raise ValueError('Expected an object')
            return value
        except (ValueError, UnicodeError) as exc:
            self.warnings.append(dict(path=str(relative), reason='JSON incomplet ou invalide : ' + type(exc).__name__))
            return None

    def lines(self, relative):
        raw = self.raw(relative)
        records = []
        if raw is None:
            return records
        lines = raw.splitlines(keepends=True)
        for number, line in enumerate(lines, 1):
            if not line.endswith(b'\n'):
                self.warnings.append(dict(path=str(relative), reason='Dernière ligne en cours d’écriture ; ignorée'))
                break
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append((number, value))
            except (ValueError, UnicodeError):
                self.warnings.append(dict(path=str(relative), reason=f'Ligne {number} invalide'))
        return records


def clip(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return text[:MAX_TEXT] + ('\n[… extrait tronqué ; consulter les preuves complètes …]' if len(text) > MAX_TEXT else '')


def authoring(e, base, tool_definitions=None):
    result = e.json(base / 'result.json', register=True)
    manifest = e.json(base / 'manifest.json') or {}
    timeline, turn, seen_messages = [], None, set()
    def add(kind, title, detail, evidence, time=None):
        timeline.append(dict(id=len(timeline), turn=turn, kind=kind, title=title,
                             detail=clip(detail), evidence=evidence, time=time))
    for line, event in e.lines(base / 'events.jsonl'):
        kind = event.get('type')
        time = event.get('observed_utc')
        proof = str(base / 'events.jsonl') + ':' + str(line)
        if kind == 'request':
            turn = event.get('id')
            add('request', f'Requête {turn} envoyée au modèle',
                'La consigne et l’historique disponible entrent dans cette requête.', proof, time)
            path = base / f'response-{turn:02d}.sse'
            raw = e.text(path, register=False)
            if raw:
                try:
                    frames = [event_frame(b) for b in raw.replace('\r\n','\n').split('\n\n') if b.strip()]
                    for item in response_items([f for f in frames if isinstance(f, dict)]):
                        typ = item.get('type')
                        if typ in ('custom_tool_call', 'function_call'):
                            add('tool', 'Appel : ' + item.get('name', '?'),
                                item.get('input', item.get('arguments', '')), str(path))
                        elif typ == 'reasoning':
                            # Only provider-exposed summaries, never encrypted or hidden reasoning.
                            texts = [v['text'] for v in item.get('summary', []) if isinstance(v, dict) and isinstance(v.get('text'), str)]
                            if texts:
                                add('explanation', 'Résumé de raisonnement émis', '\n'.join(texts), str(path))
                        elif typ == 'message':
                            texts = [v.get('text', '') for v in item.get('content', []) if isinstance(v, dict)]
                            message = '\n'.join(texts)
                            if message:
                                seen_messages.add(message)
                                add('message', 'Message de l’agent', message, str(path))
                except (ValueError, RuntimeError, TypeError, KeyError):
                    e.warnings.append(dict(path=str(path), reason='Réponse incomplète ou non reconnue'))
        elif kind == 'stdout':
            try:
                runtime = json.loads(event.get('text', ''))
            except ValueError:
                continue
            if not isinstance(runtime, dict):
                continue
            item = runtime.get('item', {})
            typ = item.get('type')
            if runtime.get('type') == 'item.completed':
                if typ == 'command_execution':
                    add('execution', 'Commande terminée · code ' + str(item.get('exit_code')),
                        item.get('command', '') + '\n\n' + item.get('aggregated_output', ''), proof, time)
                elif typ == 'file_change':
                    add('edit', 'Modification de fichier enregistrée', item.get('changes', []), proof, time)
                elif typ == 'agent_message' and item.get('text') not in seen_messages:
                    add('message', 'Message de l’agent', item.get('text', ''), proof, time)
        elif kind in ('boundary_tool_request', 'smoke_tool_request'):
            label = 'Inspection des frontières' if kind.startswith('boundary') else 'Smoke OpenMC'
            add('observation', label + ' demandé', 'Exécution séparée du modèle ; résultat à venir.', proof, time)
        elif kind == 'done':
            add('delivery', 'Session agent terminée', {'exit_code': event.get('exit_code')}, proof, time)
    trajectory = None
    # Existing exact feedback matching is reused only on completed, parseable evidence.
    if result:
        try:
            # Do not let the existing projector follow untrusted linked inputs.
            for p in confined(e.root, base).rglob('*'):
                if p.is_symlink():
                    raise ValueError('Linked builder evidence')
                if p.suffix in ('.json', '.jsonl', '.sse') and p.stat().st_size > MAX_FILE:
                    raise ValueError('Oversized builder evidence')
            trajectory = summarize(confined(e.root, base), result)
        except Exception as exc:
            e.warnings.append(dict(path=str(base), reason='Projection non disponible : ' + type(exc).__name__))
    tools = []
    for definition in (tool_definitions or catalog()['tools']):
        folder=definition.get('directory')
        if not folder: continue
        key=definition.get('legacy_projection')
        path = confined(e.root, base / folder)
        if not path.exists():
            continue
        projected = (trajectory or {}).get(key, [])
        for call in sorted(path.glob('call-*')):
            if call.is_symlink():
                continue
            relative = call.relative_to(e.root)
            feedback = e.json(relative / 'feedback.json', register=True)
            envelope=e.json(relative/'observation.json',register=True)
            envelope_status='legacy' if envelope is None else 'supported'
            if envelope is not None:
                try:
                    if envelope.get('format')!='tool-observation-v1': raise ValueError('Unsupported tool observation format')
                    if envelope.get('tool_id')!=definition['id'] or envelope.get('call_id')!=call.name: raise ValueError('Tool observation identity mismatch')
                    if envelope.get('tool_version')!=definition['version']: raise ValueError('Tool observation version mismatch')
                    for name,artifact in envelope.get('artifacts',{}).items():
                        if name not in ('request.json','response.json','feedback.json') or artifact.get('path')!=name: raise ValueError('Tool artifact outside envelope contract')
                        raw=e.raw(relative/name,register=True)
                        if raw is None or hashlib.sha256(raw).hexdigest()!=artifact.get('sha256'): raise ValueError('Tool artifact digest mismatch')
                except (ValueError,TypeError,KeyError,AttributeError) as exc:
                    envelope_status='invalid'
                    e.warnings.append(dict(path=str(relative/'observation.json'),reason=str(exc)))
            prefix = folder+'/'+call.name
            match = next((x for x in projected if x.get('evidence') == prefix or str(x.get('evidence','')).startswith(prefix+'/')), None)
            tools.append(dict(tool=definition['id'], definition=definition, envelope=envelope,envelope_status=envelope_status,call=call.name, feedback=feedback,
                projection=match, evidence=str(relative / 'feedback.json')))
            e.raw(relative / 'model.xml', register=True)
    tools.sort(key=lambda t: (t.get('projection') or {}).get('request_turn') or
               (t.get('projection') or {}).get('feedback_delivery', {}).get('inspection_request_turn') or 0)
    return dict(result=result, manifest=manifest, timeline=timeline, tools=tools, trajectory=trajectory)


def assertions(value, prefix=''):
    """Flatten existing assertions with their original fields; no new verdicts."""
    rows = []
    if isinstance(value, dict):
        if 'passed' in value or 'verdict' in value:
            rows.append(dict(path=prefix, label=value.get('requirement_id', value.get('field', prefix)),
                passed=value.get('passed'), verdict=value.get('verdict'), expected=value.get('expected'),
                actual=value.get('actual'), rule=value.get('rule'), detail=value))
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                rows.extend(assertions(child, prefix+'/'+str(key)))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            rows.extend(assertions(child, prefix+'/'+str(i)))
    return rows


def snapshot(root):
    e = Evidence(root)
    plan = e.json('plan.json', register=True) or {}
    configuration=configuration_view(plan)
    definitions={t['id']:t for t in catalog()['tools']}
    if configuration['definition']:
        definitions.update({t['id']:t for t in configuration['definition']['tools']})
    summary = e.json('summary.json', register=True)
    status = e.json('dashboard-run.json', register=True)
    cases = plan.get('cases', [])
    if not cases and confined(e.root, 'runs').is_dir():
        cases = [p.name for p in confined(e.root, 'runs').iterdir() if p.is_dir() and not p.is_symlink()]
    if not cases:
        cases = [None]
    tasks = []
    for case in cases:
        if case is not None and (not isinstance(case, str) or Path(case).name != case or case in ('.', '..')):
            e.warnings.append(dict(path='plan.json', reason='Nom de tâche invalide'))
            continue
        task = Path('runs') / case if case else Path('.')
        b = task / 'builder'
        a = task / 'assessment'
        if confined(e.root, task / 'assessment-public-demo').exists():
            a = task / 'assessment-public-demo'
        report = e.json(a / 'report.json', register=True)
        review = e.json(a / 'review.json', register=True)
        if case is None and review is None:
            review = e.json('review.json', register=True)
        builder = authoring(e, b, list(definitions.values()))
        evaluation=normalize_evaluation(report,review)
        prompt = e.text(b / 'prompt.txt') or (e.text(Path('inputs') / case / 'prompt.txt') if case else None)
        candidate = e.text(task / 'candidate.py') or e.text(a / 'candidate.py')
        xml = e.text(a / 'export/artifacts/model.xml')
        fidelity = e.json(a / 'export-fidelity.json', register=True) or (report or {}).get('fidelity') or {}
        phases = []
        for name, path in [('builder', b), ('assessment', a), ('transport', a / 'transport')]:
            for line, entry in e.lines(path / 'progress.jsonl'):
                phases.append(dict(**entry, actor=name, evidence=str(path / 'progress.jsonl')+':'+str(line)))
        phases.sort(key=lambda x: x.get('time', ''))
        phase_results = {}
        for sub in ['export', 'export-inspection', 'export-boundaries', 'transport']:
            for name in ['result.json', 'lifecycle.json']:
                value = e.json(a / sub / name, register=True)
                if name == 'result.json' and value is not None:
                    phase_results[sub] = value
        logs = {}
        for name in ['openmc-stdout.txt', 'openmc-stderr.txt', 'xml-load-stderr.txt', 'statepoint-stderr.txt']:
            text = e.text(a / 'transport' / name)
            if text is not None:
                logs[name] = clip(text)
        convergence = []
        text = e.text(a / 'transport/artifacts/convergence.csv')
        if text:
            try:
                for row in csv.DictReader(io.StringIO(text)):
                    values = [float(row[k]) for k in ('generation', 'k_generation', 'entropy_bits')]
                    if not all(math.isfinite(v) for v in values):
                        raise ValueError('Nonfinite history')
                    convergence.append(dict(generation=values[0], k=values[1], entropy=values[2], active=row['active']=='True'))
            except (ValueError, KeyError):
                convergence = []
                e.warnings.append(dict(path=str(a), reason='Historique numérique illisible'))
        identities = []
        for tool in builder['tools']:
            f = tool['feedback'] or {}
            observed = f.get('working_xml_sha256', f.get('artifact_sha256'))
            final_model = (report or {}).get('final_model')
            final = final_model.get('sha256') if isinstance(final_model, dict) else None
            identities.append(dict(label=tool['tool']+'/'+tool['call'], working_xml=observed,
                final_xml=final, identical=(observed==final) if observed and final else None))
        last = builder['tools'][-1] if builder['tools'] else None
        working_path = last['definition'].get('working_xml') if last else None
        working_xml = e.text(Path(last['evidence']).parent/working_path) if working_path else None
        diff = None
        if working_xml is not None and xml is not None:
            diff = ''.join(difflib.unified_diff(working_xml.splitlines(True), xml.splitlines(True),
                          fromfile='Dernier XML de travail observé', tofile='XML final')) or 'Aucune différence entre ces deux XML.'
        tasks.append(dict(case=case or (report or {}).get('case', 'session'), prompt=prompt,
            evaluation=evaluation,
            builder=builder, assessment_dir=str(a), report=report, review=review, fidelity=fidelity,
            assertions=assertions(fidelity), phases=phases, phase_results=phase_results, candidate=candidate, xml=xml,
            identities=identities, xml_diff=diff, convergence=convergence, logs=logs))
    return dict(format='operator-dashboard-v2', root_name=e.root.name, plan=plan, configuration=configuration, summary=summary,
                run_status=status, tasks=tasks, warnings=e.warnings, artifacts=list(e.artifacts.values()),
                interpretation='Observed evidence only; no inference of private reasoning or causal learning.')
