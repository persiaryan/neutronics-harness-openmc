"""Explicit fresh live-agent demo with public pin-cell reference; never a hidden benchmark."""
import argparse
import hashlib
from pathlib import Path
import subprocess

from experiments.run import prepare, execute, atomic_json, assessment_summary
from evaluation.candidates.run import evaluate
from evaluation.candidates.verify import review_assessment
from builder.submission import submission
from evaluator.public_runtime import load
from observability import now


def run(output, data_index, runtime_path, model='gpt-5.6-luna'):
    runtime = load(runtime_path)
    root = Path(__file__).resolve().parents[1]
    reference = root / 'examples/reflective_pin_cell/reference'
    # prepare refuses an existing directory; never reuse an authoring slot or statepoint.
    prepare(output, assistance='guided_boundaries_smoke', model=model,
            cases=('reflective_pin_cell',), smoke_data_index=data_index)
    output = Path(output)
    code = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [root/'observability.py', *sorted((root/'dashboard').glob('*.py')),
                      root/'builder/run.py', root/'evaluation/candidates/run.py', root/'evaluator/transport.py']}
    status = dict(format='dashboard-demo-v1', started=now(), state='authoring', model=model,
                  reference='public_demo_only', maximum_model_requests=8, automatic_retries=0,
                  commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=root).decode().strip(),
                  sources=code, runtime=runtime)
    atomic_json(output/'dashboard-run.json', status)
    try:
        summary = execute(output)
        row = summary['tasks'][0]
        if row['builder_status'] != 'completed':
            raise RuntimeError('Builder did not deliver a completed submission; preserved without retry')
        task = output/'runs/reflective_pin_cell'
        source, provenance = submission(task/'builder', 'reflective_pin_cell')
        if source != (task/'candidate.py').read_bytes():
            raise ValueError('Frozen submission differs from builder evidence')
        status.update(state='assessment', updated=now())
        atomic_json(output/'dashboard-run.json', status)
        folder = task/'assessment-public-demo'
        report = evaluate('reflective_pin_cell', folder, index=data_index, candidate=task/'candidate.py',
                          provenance=provenance, reference=reference, runtime=runtime)
        status.update(state='verification', updated=now())
        atomic_json(output/'dashboard-run.json', status)
        review = review_assessment(folder, data_index, reference=reference, runtime=runtime)
        atomic_json(folder/'review.json', review)
        row.update(assessment_summary(report, review), final_assessment=report['status'],
                   assessment='runs/reflective_pin_cell/assessment-public-demo')
        summary['transport'] = 'native_final_assessment_run'
        atomic_json(output/'summary.json', summary)
        status.update(state='finished', finished=now(), evidence_status=review['evidence_status'],
                      verified_protocol_success=row['overall_success'])
        return row
    except Exception as exc:
        status.update(state='stopped', finished=now(), error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        atomic_json(output/'dashboard-run.json', status)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--data-index', type=Path, required=True)
    p.add_argument('--model', default='gpt-5.6-luna')
    args = p.parse_args()
    row = run(args.output, args.data_index, args.runtime, args.model)
    print('Session terminée. Succès vérifié :', row['overall_success'])
    raise SystemExit(0 if row['overall_success'] else 1)


if __name__ == '__main__':
    main()
