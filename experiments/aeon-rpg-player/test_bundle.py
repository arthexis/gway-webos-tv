import hashlib
import io
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zipfile
import bundle_player as bundle

HERE = Path(__file__).resolve().parent


def elf(kind=3, machine=40, flags=0x05000200):
    data = bytearray(52)
    data[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HH', data, 16, kind, machine)
    struct.pack_into('<I', data, 36, flags)
    return data


class BundleTests(unittest.TestCase):
    def test_abi(self):
        bundle.arm_elf(elf(), (3,))
        for data in (b'not ELF', elf(machine=183), elf(flags=0x05000400), elf(kind=2)):
            with self.assertRaises(ValueError): bundle.arm_elf(data, (3,))

    def test_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input'; p.write_bytes(b'input')
            self.assertEqual(bundle.checked(p,hashlib.sha256(b'input').hexdigest()),b'input')
            with self.assertRaises(ValueError): bundle.checked(p,'0'*64)

    def test_fixture_allowlist(self):
        with tempfile.TemporaryDirectory() as d:
            for unexpected in (False, True):
                b=io.BytesIO()
                with zipfile.ZipFile(b,'w') as z:
                    z.writestr('Game.ini','[Game]'); z.writestr('Data/Scripts.rvdata2',b'fixture')
                    if unexpected: z.writestr('../escape',b'x')
                if unexpected:
                    with self.assertRaises(ValueError): bundle.fixture(b.getvalue(),Path(d))
                else:
                    bundle.fixture(b.getvalue(),Path(d)); self.assertTrue((Path(d)/'fixture/Game.ini').is_file())

    def test_launcher_keeps_config(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); home=root/'home'; home.mkdir(); app=root/'app'; app.mkdir()
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(HERE/'launcher.c'),'-o',str(app/'launcher')],check=True)
            front=app/'retroarch'; front.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n'); front.chmod(0o755)
            env={**os.environ,'HOME':str(home)}
            if Path('/media/internal').is_dir() and os.access('/media/internal',os.W_OK): self.skipTest('host has actual media directory')
            r=subprocess.check_output([str(app/'launcher')],env=env,text=True)
            data=home/'.aeon-rpg-player'; cfg=data/'retroarch.cfg'
            self.assertIn(str(app/'fixture/Game.ini'),r); self.assertIn(str(data/'saves'),cfg.read_text())
            self.assertTrue((data/'games').is_dir()); cfg.write_text('preserved\n')
            subprocess.run([str(app/'launcher')],env=env,check=True,capture_output=True)
            self.assertEqual(cfg.read_text(),'preserved\n')
