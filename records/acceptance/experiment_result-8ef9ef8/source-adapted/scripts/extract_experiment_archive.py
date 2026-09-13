"""Verify and extract one evidence archive into a NEW directory (no overwrite)."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def extract(manifest_path, destination):
    manifest_path = Path(manifest_path).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Destination must be a new directory; original files are never overwritten')
    manifest = json.loads(manifest_path.read_text())
    expected = {m['path']: m for m in manifest['members']}
    if len(expected) != len(manifest['members']):
        raise ValueError('Duplicate manifest member')
    with tempfile.TemporaryDirectory(prefix='paper-evidence-') as tmp:
        archive = Path(tmp) / 'data.tar.gz'
        with archive.open('wb') as output:
            for part in manifest['parts']:
                p = manifest_path.parent / part['file']
                if p.parent != manifest_path.parent or p.stat().st_size != part['bytes'] or digest(p) != part['sha256']:
                    raise ValueError(f'Invalid archive part: {p}')
                with p.open('rb') as src:
                    shutil.copyfileobj(src, output)
        if digest(archive) != manifest['archive_sha256']:
            raise ValueError('Archive hash mismatch')
        # Validate every member before creating the destination.
        with tarfile.open(archive, 'r:gz') as tar:
            seen = set()
            for member in tar:
                name = PurePosixPath(member.name)
                if not member.isfile() or name.is_absolute() or '..' in name.parts or '\\' in member.name or member.name not in expected or member.name in seen:
                    raise ValueError(f'Unsafe/unexpected member: {member.name}')
                with tar.extractfile(member) as src:
                    h = hashlib.file_digest(src, 'sha256').hexdigest()
                if h != expected[member.name]['sha256'] or member.size != expected[member.name]['bytes']:
                    raise ValueError(f'Member mismatch: {member.name}')
                seen.add(member.name)
            if seen != set(expected):
                raise ValueError('Missing members')
        destination.mkdir(parents=True, exist_ok=False)
        with tarfile.open(archive, 'r:gz') as tar:
            for member in tar:
                path = destination / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, path.open('xb') as output:
                    shutil.copyfileobj(src, output)
    return len(expected)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('destination', type=Path)
    args = p.parse_args()
    print(json.dumps({'verified_extracted_files': extract(args.manifest, args.destination)}, indent=2))
