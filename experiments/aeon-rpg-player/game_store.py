"""Host-side reference for immutable game releases and independent saves."""
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
import fcntl

TOKEN = re.compile(r'[a-z0-9][a-z0-9._-]{0,79}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
FIELDS = {'id', 'title', 'engine', 'version', 'sha256', 'entry', 'input_profile'}
MAX_FILES = 20000
MAX_BYTES = 2 * 1024**3


def token(value):
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        raise ValueError('invalid identifier')
    return value


def parts(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or any(ord(c) < 32 for c in name):
        raise ValueError('invalid archive path')
    p = name.split('/')
    if any(x in {'', '.', '..'} for x in p):
        raise ValueError('unsafe archive path')
    return p


def validate(m):
    if not isinstance(m, dict) or set(m) != FIELDS:
        raise ValueError('invalid manifest fields')
    for field in ('id', 'version', 'input_profile'):
        token(m[field])
    if m['engine'] not in ('rgss1', 'rgss2', 'rgss3'):
        raise ValueError('unsupported engine')
    if not isinstance(m['title'], str) or not m['title'].strip() or len(m['title']) > 200:
        raise ValueError('invalid title')
    if not isinstance(m['sha256'], str) or not SHA.fullmatch(m['sha256']):
        raise ValueError('invalid checksum')
    if parts(m['entry']) != ['Game.ini']:
        raise ValueError('entry must be root Game.ini')
    return m


def extract(archive, target):
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > MAX_FILES or sum(x.file_size for x in infos) > MAX_BYTES:
            raise ValueError('archive exceeds limits')
        seen, prefixes = set(), {}
        for info in infos:
            name = info.filename[:-1] if info.is_dir() else info.filename
            components = parts(name)
            folded = name.casefold()
            if folded in seen or components[0].casefold() == '.aeon-manifest.json':
                raise ValueError('duplicate or reserved path')
            seen.add(folded)
            for i in range(1, len(components)+1):
                prefix = '/'.join(components[:i])
                if prefixes.setdefault(prefix.casefold(), prefix) != prefix:
                    raise ValueError('case collision')
            mode = stat.S_IFMT(info.external_attr >> 16)
            if mode not in (0, stat.S_IFREG, stat.S_IFDIR) or (mode and (mode == stat.S_IFDIR) != info.is_dir()):
                raise ValueError('unsupported archive entry type')
            p = target.joinpath(*components)
            if info.is_dir():
                p.mkdir(parents=True, exist_ok=True)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, p.open('xb') as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)


@contextmanager
def lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def activate_pointer(game, version):
    fd, name = tempfile.mkstemp(prefix='.current-', dir=game)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(version + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, game / 'current')
    finally:
        Path(name).unlink(missing_ok=True)


def release_manifest(release):
    m = validate(json.loads((release / '.aeon-manifest.json').read_text()))
    if m['version'] != release.name or m['id'] != release.parent.parent.name or not (release / m['entry']).is_file():
        raise ValueError('invalid installed release')
    return m


def install(root, manifest, archive):
    m = validate(manifest)
    root = Path(root)
    with lock(root), Path(archive).open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != m['sha256']:
            raise ValueError('checksum mismatch')
        source.seek(0)
        game = root / m['id']
        versions = game / 'versions'
        versions.mkdir(parents=True, exist_ok=True)
        release = versions / m['version']
        if release.exists():
            if release_manifest(release) != m:
                raise ValueError('version collision')
        else:
            with tempfile.TemporaryDirectory(prefix='.stage-', dir=versions) as tmp:
                stage = Path(tmp) / 'release'
                stage.mkdir()
                extract(source, stage)
                if not (stage / m['entry']).is_file():
                    raise ValueError('game entry missing')
                (stage / '.aeon-manifest.json').write_text(json.dumps(m, sort_keys=True))
                stage.rename(release)
        (game / 'saves').mkdir(exist_ok=True)
        activate_pointer(game, m['version'])
        return release


def select(root, game_id, version):
    root = Path(root)
    with lock(root):
        game = root / token(game_id)
        release = game / 'versions' / token(version)
        release_manifest(release)
        activate_pointer(game, version)
        return release


def catalog(root):
    root = Path(root)
    with lock(root):
        result = []
        for game in sorted(root.iterdir()):
            if game.is_dir() and (game / 'current').is_file():
                version = token((game / 'current').read_text().strip())
                result.append(release_manifest(game / 'versions' / version))
        return result


def deactivate(root, game_id):
    """Remove from catalog without destroying releases or saved games."""
    root = Path(root)
    with lock(root):
        (root / token(game_id) / 'current').unlink(missing_ok=True)
