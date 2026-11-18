"""Run browser-independent Connect Four rule tests in CI without npm installs."""
from pathlib import Path
import shutil
import subprocess


def test_connect_four_rules_offline():
    node = shutil.which('node')
    assert node is not None, 'Node.js is required for offline game rule tests'
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [node, '--test', 'tests/test_connect_four_rules.js'],
        cwd=root, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
