"""Exercise the real release-manifest generator in a temporary directory."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("version", ["1.2.3", "2.0.0-beta.1"])
def test_release_manifest_includes_tested_minimum_dependency(tmp_path, version):
    """Follow HA's shared package upgrades while retaining the tested minimum."""
    root = Path(__file__).parents[1]
    component = tmp_path / "custom_components/pun_sensor"
    component.mkdir(parents=True)
    shutil.copy(root / "custom_components/pun_sensor/manifest.json", component)
    shutil.copy(root / "requirements.txt", tmp_path)
    subprocess.run(
        [
            sys.executable,
            "-B",
            str(root / ".github/workflows/update_manifest.py"),
            "--version",
            version,
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = json.loads((component / "manifest.json").read_text())
    assert manifest["version"] == version
    assert manifest["requirements"] == ["holidays>=0.108"]
    assert manifest["domain"] == "pun_sensor"
