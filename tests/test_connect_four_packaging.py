"""Third offline app: manifest validation, staging, and packaged assets."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('c4_tv_app', ROOT / 'scripts/tv-app.py')


def test_connect_four_offline_manifest_and_staging(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = ROOT / 'apps/connect-four'
    manifest, meta = module.load_manifest(app)
    assert manifest == {
        'schema': 'gway-webos-tv/app-build/v1',
        'entry': 'index.html',
        'bridge': {'mode': 'none'},
    }
    assert meta['id'] == 'com.arthexis.gway.connectfour'
    assert meta['main'] == 'index.html'
    assert 'connect-four' in module.discover_apps()
    original = {name: (app / name).read_bytes() for name in ('game.js', 'index.html', 'icon.png')}
    staged = tmp_path / 'stage'
    module.stage_app(app, staged, manifest, tmp_path / 'missing-wss-credentials.json')
    assert not (staged / 'manifest.json').exists()
    for name, contents in original.items():
        assert (staged / name).read_bytes() == contents
        assert (app / name).read_bytes() == contents
    assert (staged / 'icon.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert len((staged / 'icon.png').read_bytes()) > 100
    assert (ROOT / 'LICENSE').read_text().startswith('MIT License')
    page = (staged / 'index.html').read_text().lower()
    assert '<script src="game.js"></script>' in page
    assert not any(token in page for token in ('http://', 'https://', 'wss://', 'cdn.'))


def test_connect_four_does_not_require_bridge_config(tmp_path, monkeypatch):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def fake_command(tool, *args):
        assert tool == 'ares-package'
        output_root = Path(args[1])
        staged = Path(args[2])
        assert (staged / 'icon.png').is_file()
        assert (staged / 'game.js').is_file()
        assert not (staged / 'manifest.json').exists()
        info = json.loads((staged / 'appinfo.json').read_text())
        (output_root / f"{info['id']}_{info['version']}_all.ipk").write_bytes(b'mocked-ipk')
        return ''
    monkeypatch.setattr(module, 'command', fake_command)
    monkeypatch.setattr('sys.argv', [
        'tv-app.py', 'connect-four', '--config', str(tmp_path / 'nonexistent.json'),
        '--output-dir', str(tmp_path / 'out'),
    ])
    assert module.main() == 0
    assert len(list((tmp_path / 'out').glob('*.ipk'))) == 1
