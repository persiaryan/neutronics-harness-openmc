"""Factory driver, staged ONLY inside the isolated candidate container.

This shares the candidate interpreter and is not a security boundary. Diagnostics
are untrusted internal reports. The separate observer retains execution receipts;
fresh XML admission/inspection is still required. Never import this on the host.
"""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

import openmc


class DeliveryError(Exception):
    pass


def snapshot():
    """Bounded metadata snapshot of writable locations; no symlink traversal."""
    result = {}
    pending = [Path('/work'), Path('/tmp'), Path('/input')]
    while pending:
        path = pending.pop()
        info = path.lstat()
        result[str(path)] = (info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if len(result) > 256:
            raise DeliveryError('Writable filesystem exceeds observation coverage')
        if stat.S_ISDIR(info.st_mode):
            pending.extend(path.iterdir())
    return result


def main():
    phase = 'driver_setup'
    def diagnostic(event, **detail):
        print(json.dumps(dict(format='factory-driver-diagnostic-v1', authority='candidate_interpreter',
                              phase=phase, event=event, **detail)), file=sys.stderr, flush=True)
    try:
        if openmc.__version__ != '0.15.3':
            raise RuntimeError('Factory driver requires OpenMC 0.15.3')
        model_type = openmc.Model
        export = model_type.export_to_model_xml
        before = snapshot()
        if list(Path('/work').iterdir()):
            raise DeliveryError('Export location is not fresh')
        violations = []

        def audit(event, args):
            # Practical observable prohibitions, not a Python purity verifier.
            if phase not in ('module_loading', 'entrypoint_resolution', 'construction', 'return_contract'):
                return
            forbidden = event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec', 'os.fork')
            if event == 'open' and isinstance(args[0], (str, bytes)):
                path, mode, flags = args
                writes = bool((flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
                forbidden = writes and os.fsdecode(path).lower().endswith(('.xml', '.h5'))
            if forbidden:
                violations.append(event)
                raise DeliveryError('Prohibited observable export/process operation: ' + event)

        sys.addaudithook(audit)
        phase = 'module_loading'; diagnostic('started')
        spec = importlib.util.spec_from_file_location('candidate', '/input/candidate.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules['candidate'] = module
        spec.loader.exec_module(module)
        if violations or snapshot() != before:
            raise DeliveryError('Observable side effect during module loading')
        phase = 'entrypoint_resolution'; diagnostic('started')
        factory = getattr(module, 'build_model', None)
        if not callable(factory):
            raise DeliveryError('build_model is missing or not callable')
        phase = 'construction'; diagnostic('started')
        model = factory()
        if violations or snapshot() != before:
            raise DeliveryError('Observable side effect during construction')
        phase = 'return_contract'; diagnostic('started')
        if not isinstance(model, model_type):
            raise DeliveryError('build_model did not return an openmc.Model')
        phase = 'export'; diagnostic('started')
        # Unbound pinned method, using exactly the returned object. No repairs,
        # global model lookup, script fallback or optional-attribute restrictions.
        export(model, path='/work/model.xml')
        diagnostic('completed')
    except Exception as exc:
        diagnostic('failed', error_type=type(exc).__name__, detail=str(exc)[:1000])
        raise  # Preserve traceback and ordinary exception exit behavior.
    # SystemExit, os._exit, signals and observer budget stops are not collapsed.


if __name__ == '__main__':
    main()
