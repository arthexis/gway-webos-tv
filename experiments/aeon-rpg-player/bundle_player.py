"""Assemble an operator-local AEon player from reviewed, hashed inputs."""
import argparse
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile
import tempfile
import zipfile
import zlib

FRONTEND_SHA = '0b8ead78b49f02097986a14776d1d90ce856184a11290e8c3640f1001b02d4e3'
FRONTEND_ROOT = 'usr/palm/applications/com.retroarch.webos/'
FRONTEND_FILES = {'appinfo.json', 'icon160.png', 'retroarch', 'lib/libSDL2-2.0.so.0', 'lib/libatomic.so.1', 'lib/libstdc++.so.6'}
FIXTURE_FILES = {'Game.ini', 'Data/Scripts.rvdata2'}
APP_ID = 'com.arthexis.aeon.rpgplayer'


def checked(path, digest):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f'checksum mismatch: {Path(path).name}')
    return data


def arm_elf(data, kind):
    if len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('expected little-endian ELF32')
    elf_type, machine = struct.unpack_from('<HH', data, 16)
    flags, = struct.unpack_from('<I', data, 36)
    if machine != 40 or elf_type not in kind or flags & 0x400 or flags >> 24 != 5:
        raise ValueError('expected ARM EABI5 non-hardfloat ELF')



def glibc_gate(path):
    versions = subprocess.check_output(['readelf', '--version-info', str(path)], text=True)
    required = [tuple(map(int, v.split('.'))) for v in re.findall(r'GLIBC_([0-9]+(?:\.[0-9]+)+)', versions)]
    if any(v > (2, 31) for v in required):
        raise ValueError(f'{path.name} requires GLIBC newer than TV 2.31')


def make_icon(path):
    def chunk(t, data):
        return struct.pack('>I', len(data)) + t + data + struct.pack('>I', zlib.crc32(t + data) & 0xffffffff)
    rows=[]
    for y in range(160):
        row=bytearray()
        for x in range(160):
            ring=900 < (x-80)**2+(y-80)**2 < 3600
            pad=35<x<125 and 70<y<105
            row.extend((96,225,175) if ring else (104,119,177) if pad else (19,27,46))
        rows.append(b'\0'+row)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',160,160,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b''))


def frontend(ipk, stage):
    checked(ipk, FRONTEND_SHA)
    data = subprocess.check_output(['ar', 'p', str(ipk), 'data.tar.gz'])
    found = set()
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for m in archive.getmembers():
            name = m.name.removeprefix('./')
            if not name.startswith(FRONTEND_ROOT) or m.isdir():
                continue
            rel = name[len(FRONTEND_ROOT):]
            if rel not in FRONTEND_FILES or rel in found or not m.isfile():
                raise ValueError('unexpected frontend entry')
            found.add(rel)
            p = stage / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            contents = archive.extractfile(m).read()
            if rel == 'retroarch' or rel.startswith('lib/'):
                arm_elf(contents, (2, 3) if rel == 'retroarch' else (3,))
            p.write_bytes(contents)
            p.chmod(0o755 if rel == 'retroarch' else 0o644)
    if found != FRONTEND_FILES:
        raise ValueError('incomplete frontend')
    meta = json.loads((stage / 'appinfo.json').read_text())
    if meta.get('id') != 'com.retroarch.webos' or meta.get('version') != '1.22.2' or meta.get('type') != 'native':
        raise ValueError('frontend identity mismatch')
    meta.update(id=APP_ID, title='AEon RPG Player', main='launcher', version='0.1.0', vendor='Arthexis', appDescription='Local RPG Maker player (experimental)')
    (stage / 'appinfo.json').write_text(json.dumps(meta, indent=2)+'\n')


def fixture(data, stage):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if set(z.namelist()) != FIXTURE_FILES or len(z.infolist()) != len(FIXTURE_FILES):
            raise ValueError('unexpected fixture members')
        for info in z.infolist():
            if info.file_size > 1024*1024:
                raise ValueError('oversized fixture')
            p = stage / 'fixture' / info.filename
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(z.read(info))


def assemble(args, stage):
    frontend(args.frontend, stage)
    core = checked(args.core, args.core_sha)
    launcher = checked(args.launcher, args.launcher_sha)
    arm_elf(core, (3,)); arm_elf(launcher, (2, 3))
    (stage / 'cores').mkdir()
    (stage / 'cores/mkxp-z_libretro.so').write_bytes(core)
    (stage / 'launcher').write_bytes(launcher)
    (stage / 'launcher').chmod(0o755)
    for binary in (stage/'retroarch', stage/'launcher', stage/'cores/mkxp-z_libretro.so', *(stage/'lib').iterdir()):
        glibc_gate(binary)
    make_icon(stage/'icon160.png')
    fixture(checked(args.fixture, args.fixture_sha), stage)
    licenses = stage / 'licenses'; licenses.mkdir()
    for name, src in [('RetroArch-COPYING', args.frontend_license), ('mkxp-z-COPYING', args.core_license)]:
        shutil.copyfile(src, licenses / name)
    provenance = dict(frontend='webosbrew/RetroArch v1.22.2', frontend_sha256=FRONTEND_SHA,
                      core_revision='ef4d336850bf749b531386522109a165c002354b', core_sha256=args.core_sha,
                      launcher_sha256=args.launcher_sha, fixture_sha256=args.fixture_sha,
                      purpose='private lab evaluation only; redistribution review pending')
    (stage / 'AEON-PROVENANCE.json').write_text(json.dumps(provenance, indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('frontend','core','core-sha','launcher','launcher-sha','fixture','fixture-sha','frontend-license','core-license','output'):
        p.add_argument('--'+name, required=True)
    args=p.parse_args()
    output=Path(args.output).resolve()
    output.mkdir(mode=0o700, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('output directory must be empty')
    with tempfile.TemporaryDirectory(prefix='aeon-bundle-') as temp:
        stage=Path(temp) / 'app'; stage.mkdir()
        assemble(args, stage)
        node=os.environ.get('WEBOS_NODE_BIN', str(Path.home()/'.local/opt/webos-node24/node_modules/node/bin/node'))
        cli=Path(os.environ.get('WEBOS_CLI_DIR', str(Path.home()/'.local/opt/webos-tools/node_modules/@webos-tools/cli/bin')))
        subprocess.run([node,str(cli/'ares-package.js'),str(stage),'-o',str(output)],check=True,env={**os.environ,'NODE_OPTIONS':'--no-addons'})
    ipks=list(output.glob('*.ipk'))
    if len(ipks)!=1 or ipks[0].name != APP_ID+'_0.1.0_arm.ipk':
        raise ValueError('unexpected package output')
    digest=hashlib.sha256(ipks[0].read_bytes()).hexdigest()
    (output/'SHA256SUMS').write_text(f'{digest}  {ipks[0].name}\n')
    print(digest,ipks[0])


if __name__=='__main__':
    main()
