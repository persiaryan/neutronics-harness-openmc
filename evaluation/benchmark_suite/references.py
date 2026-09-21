"""Read and verify the existing six frozen reference packages; never generate them."""
import json
import stat
from pathlib import Path
from evaluator.run import digest
from evaluation.scientific.records import require
from prompts.prepare import read_public_text,CASE_FILES
ROOT=Path(__file__).resolve().parents[2]
INDEX=Path(__file__).with_name('frozen')/'pilot-1'
MAX_FILES=1500
MAX_BYTES=512_000_000
def inventory(root,exclude=()):
    root=Path(root)
    require(root.is_dir() and not root.is_symlink(),'Package root must be a real directory')
    records={};total=0
    for path in sorted(root.rglob('*')):
        info=path.lstat()
        require(not path.is_symlink(),'Links are not supported in frozen evidence')
        if path.is_dir():continue
        require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'Only ordinary, unlinked files may be frozen')
        relative=path.relative_to(root).as_posix()
        if relative in exclude:continue
        require(info.st_size<=32_000_000,'Individual frozen artifact exceeds byte budget')
        raw=path.read_bytes();total+=len(raw)
        records[relative]={'bytes':len(raw),'sha256':digest(raw)}
        require(len(records)<=MAX_FILES and total<=MAX_BYTES,'Frozen package exceeds limits')
    return records
def verify_package(output):
    output=Path(output)
    # Inventory checks links and special files before metadata is trusted.
    actual=inventory(output)
    require('manifest.json' in actual and 'seal.sha256' in actual,'Package is not sealed')
    raw=(output/'manifest.json').read_bytes();seal=(output/'seal.sha256').read_text().strip()
    require(digest(raw)==seal,'Freeze manifest seal mismatch')
    manifest=json.loads(raw)
    require(manifest['format']=='frozen-reference-evidence-v1' and manifest['grading_enabled'] is False,
            'Unexpected freeze type or unapproved grading activation')
    files={k:v for k,v in actual.items() if k not in {'manifest.json','seal.sha256'}}
    require(files==manifest['files'],'Frozen file inventory or bytes changed')
    return {'status':'verified','manifest_sha256':seal,'files':len(files),'technical_status':manifest['technical_status'],
            'scientific_review':manifest['scientific_review'],'grading_enabled':False}


def expected_data(case,data):
    return dict(data,files={k:v for k,v in data['files'].items() if not k.startswith('Zr')}) if case=='moderated_cylinder' else data


def verify(output=INDEX):
    output=Path(output)
    files=inventory(output)
    raw=(output/'manifest.json').read_bytes();manifest=json.loads(raw)
    require((output/'seal.sha256').read_text().strip()==digest(raw),'Suite seal changed')
    require(manifest['format']=='frozen-six-case-suite-v1' and manifest['grading_enabled'] is False and
            manifest['scientific_review']=='pending_owner_review','Invalid suite format/approval')
    require({k:v for k,v in files.items() if k not in {'manifest.json','seal.sha256'}}==manifest['files'],'Suite inventory changed')
    require(set(manifest['references'])==set(CASE_FILES),'Incomplete six-task reference inventory')
    for case,ref in manifest['references'].items():
        require(ref['path']=='evaluation/'+case+'/frozen/v1','Unexpected reference location')
        folder=ROOT/ref['path'];checked=verify_package(folder)
        package=json.loads((folder/'manifest.json').read_bytes())
        report=json.loads((folder/'evidence/qualification.json').read_bytes())
        require(package['case']==case and package['case_version']==1 and
                report['case']==case and report['status']==package['technical_status'] and
                report['primary_mean']==package['primary_mean']==ref['primary_mean'], 'Reference summary changed')
        require(checked['manifest_sha256']==ref['manifest_sha256'] and
                checked['technical_status']==ref['technical_status'], 'Reference identity changed')
        # Frozen packages retain their original delivery instructions as history.
        # Bind public physics text directly; no active legacy prompt renderer.
        prompt=(folder/'evidence/public-prompt/prompt.txt').read_bytes()
        require(digest(prompt)==ref['public_prompt_sha256'] and
                prompt.endswith(read_public_text(CASE_FILES[case]).rstrip().encode()+b'\n'), 'Reference task specification changed')
    return dict(status='verified',cases=6,manifest_sha256=digest(raw),grading_enabled=False,
                technical_statuses={c:r['technical_status'] for c,r in manifest['references'].items()})
