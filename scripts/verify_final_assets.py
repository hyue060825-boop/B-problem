"""只读核验最终资产、来源映射、冻结源码、原始数据及当前说明链接。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import statistics
import subprocess
import tarfile
import tempfile
from urllib.parse import unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT/'records/acceptance/experiment_result-8ef9ef8'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'.local/final-assets-verification.json')
    parser.add_argument('--deep-archives', action='store_true')
    args = parser.parse_args()
    failures, checks = [], {}
    def require(ok, message):
        if not ok:
            failures.append(message)
    mapping = read(RECORD/'asset-map-main.json')
    with zipfile.ZipFile(ROOT/'deployment/bundles/B-problem-paper-final.zip') as bundle:
        for row in mapping['files']:
            target = row['target']
            if '::' in target:
                digest = hashlib.sha256(bundle.read(target.split('::', 1)[1])).hexdigest()
            else:
                digest = sha(ROOT/target) if (ROOT/target).is_file() else None
            require(digest == row['target_sha256'], 'mapped target: '+target)
            if row['unchanged']:
                require(digest == row['source_sha256'], 'original bytes: '+row['source_path'])
            if row['original_copy']:
                require(sha(ROOT/row['original_copy']) == row['source_sha256'], 'source copy: '+row['source_path'])
    expected = subprocess.check_output(['git', 'ls-tree', '-rz', '--name-only', mapping['source_commit']], cwd=ROOT).decode().strip('\0').split('\0')
    require(set(expected) == {r['source_path'] for r in mapping['files']}, 'incomplete source mapping')
    checks['mapped_source_files'] = len(mapping['files'])
    checks['byte_identical_targets'] = sum(r['unchanged'] for r in mapping['files'])
    protected = ['paper', 'src', 'problem', 'results/final-8ef9ef8', 'docs/references',
                 'experiments/q2', 'records/improvements', 'handoff/q1', 'handoff/q2',
                 'handoff/tables/LIT-Q2-01', 'handoff/shared/文献启发与Q2改进说明.md']
    # 原整合基准保留；论文手后续已接收的 main 更新使用新的保护基准。
    protected_base = mapping.get('protected_main_base', mapping['main_base'])
    changed = subprocess.check_output(['git', 'diff', '--name-only', protected_base, '--', *protected], cwd=ROOT, text=True)
    require(not changed.strip(), 'main protected assets changed: '+changed)
    checks['main_protected_paths_unchanged'] = not changed.strip()
    checks['protected_main_base'] = protected_base
    models = read(ROOT/'records/inventory/models-final-20260913.json')['models']
    for model in models:
        require(sha(ROOT/model['path']) == model['sha256'], 'model: '+model['id'])
        for path, digest in model['runtime_files'].items():
            require(sha(ROOT/model['runtime_root']/path) == digest, 'runtime: '+path)
    checks['models'] = len(models)
    checks['runtime_files_per_model'] = len(models[0]['runtime_files'])
    for path, digest in read(RECORD/'table-inputs-main.json').items():
        require(sha(ROOT/path) == digest, 'table input: '+path)
    # 核对新表的证据与两侧逐局记录，避免只检查候选均值。
    with (ROOT/'handoff/tables/final-20260913/final_main_results.csv').open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        data = read(ROOT/row['evidence'])
        if row['model'].startswith('q4_'):
            data = data['baseline' if row['model'].endswith('parent') else 'student']
        require(len(data) == int(row['episodes']) == 3000, 'sample count: '+row['model'])
        require(all(r['completion'] and r['C'] == r['N'] and not r['error'] for r in data), 'completion: '+row['model'])
        require(abs(statistics.mean(r['virtual_time_s'] for r in data)-float(row['mean_T_s'])) < 1e-8, 'T mean: '+row['model'])
        require(abs(statistics.mean(r['virtual_time_s']/r['N'] for r in data)-float(row['mean_T_per_N_s'])) < 1e-8, 'T/N mean: '+row['model'])
    checks['main_raw_records_recomputed'] = sum(int(r['episodes']) for r in rows)
    manifests = sorted((ROOT/'results/history/experiment_result-8ef9ef8').rglob('archive_manifest.json'))
    parts, members = 0, 0
    for path in manifests:
        manifest = read(path)
        digest = hashlib.sha256()
        with tempfile.TemporaryFile() as assembled:
            for part in manifest['parts']:
                p = path.parent/part['file']
                require(p.parent == path.parent and p.stat().st_size == part['bytes'] and sha(p) == part['sha256'], 'part: '+str(p))
                with p.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024*1024), b''):
                        digest.update(chunk)
                        if args.deep_archives:
                            assembled.write(chunk)
                parts += 1
            require(digest.hexdigest() == manifest['archive_sha256'], 'assembled archive: '+str(path))
            if args.deep_archives:
                expected = {m['path']: m for m in manifest['members']}
                seen = set()
                assembled.seek(0)
                with tarfile.open(fileobj=assembled, mode='r|gz') as archive:
                    for member in archive:
                        name = PurePosixPath(member.name)
                        valid = member.isfile() and not name.is_absolute() and '..' not in name.parts and member.name in expected and member.name not in seen
                        require(valid, 'unexpected member: '+member.name)
                        if not valid:
                            continue
                        with archive.extractfile(member) as stream:
                            h = hashlib.file_digest(stream, 'sha256').hexdigest()
                        require(h == expected[member.name]['sha256'] and member.size == expected[member.name]['bytes'], 'member: '+member.name)
                        seen.add(member.name)
                require(seen == set(expected), 'missing archive members: '+str(path))
                members += len(seen)
    checks['archives'] = dict(archives=len(manifests), parts=parts, members_read=members,
                             member_check='streamed hashes' if args.deep_archives else 'not rerun; use --deep-archives')
    paths = [ROOT/'README.md', ROOT/'AGENTS.md', ROOT/'github-guidance.md', ROOT/'deployment/README.md',
             ROOT/'scripts/README.md', ROOT/'results/final-20260913/README.md', ROOT/'records/README.md', ROOT/'records/versions.md']
    for folder in ('docs', 'handoff'):
        paths.extend((ROOT/folder).rglob('*.md'))
    links = 0
    for path in paths:
        for raw in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            target = unquote(raw.strip('<>').split('#', 1)[0])
            if not target or '://' in target:
                continue
            require((path.parent/target).exists(), f'link: {path.relative_to(ROOT)} -> {target}')
            links += 1
    checks['current_links'] = links
    checks['server_cache'] = 'Not in this delivery; no claim that all historical weights are backed up.'
    result = dict(status='FAIL' if failures else 'PASS', source_commit=mapping['source_commit'],
                  main_base=mapping['main_base'], checks=checks, failures=failures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
