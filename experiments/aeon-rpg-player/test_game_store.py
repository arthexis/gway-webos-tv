import hashlib
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from game_store import install, select, catalog, deactivate


class GameStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'library'

    def bundle(self, version='1', entries=None):
        archive = self.base / 'bundle.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for name, content in (entries if entries is not None else [('Game.ini', 'game '+version), ('Data/Scripts.rvdata2', 'fixture')]):
                z.writestr(name, content)
        manifest = dict(id='aeon-fixture', title='AEon fixture', engine='rgss3', version=version,
                        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), entry='Game.ini', input_profile='snes')
        return manifest, archive

    def test_update_rollback_and_deactivate_preserve_saves(self):
        old = install(self.root, *self.bundle())
        saved = old.parent.parent / 'saves' / 'Save01.rvdata2'
        saved.write_bytes(b'save')
        bundle = self.bundle('2')
        new = install(self.root, *bundle)
        self.assertEqual(catalog(self.root)[0]['version'], '2')
        self.assertEqual(install(self.root, *bundle), new)
        self.assertEqual(select(self.root, 'aeon-fixture', '1'), old)
        self.assertEqual(catalog(self.root)[0]['version'], '1')
        self.assertEqual(saved.read_bytes(), b'save')
        deactivate(self.root, 'aeon-fixture')
        self.assertEqual(catalog(self.root), [])
        self.assertEqual(saved.read_bytes(), b'save')
        self.assertTrue(new.exists())

    def test_failure_keeps_current(self):
        install(self.root, *self.bundle())
        m, z = self.bundle('2'); m['sha256'] = '0'*64
        with self.assertRaises(ValueError): install(self.root, m, z)
        with self.assertRaises(ValueError): install(self.root, *self.bundle('1', [('Game.ini', 'different')]))
        with self.assertRaises(ValueError): install(self.root, *self.bundle('2', [('not-game', 'x')]))
        self.assertEqual(catalog(self.root)[0]['version'], '1')

    def test_unsafe_archive_paths(self):
        symlink = zipfile.ZipInfo('symlink'); symlink.create_system = 3; symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        for entry in ['../escape', '/absolute', 'a/../../escape', 'a\\b', 'C:/escape', '.aeon-manifest.json', 'game.ini', symlink]:
            with self.subTest(entry=entry):
                with self.assertRaises(ValueError): install(self.root, *self.bundle(entries=[('Game.ini', 'x'), (entry, 'x')]))
        self.assertFalse((self.base / 'escape').exists())
        self.assertEqual(catalog(self.root), [])

    def test_invalid_manifest(self):
        m, z = self.bundle()
        for field, value in [('id','../bad'), ('version','../../bad'), ('entry','/Game.ini'), ('engine','exe'), ('input_profile','../bad')]:
            with self.subTest(field=field):
                with self.assertRaises(ValueError): install(self.root, {**m, field:value}, z)


if __name__ == '__main__':
    unittest.main()
