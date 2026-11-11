import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_launcher_is_location_relative_and_supports_dev_and_portable():
    launcher = (PROJECT_ROOT / "run-karaoke-studio.bat").read_text(encoding="utf-8")
    assert "%~dp0" in launcher
    assert "MT-Karaoke-Studio.exe" in launcher
    assert ".venv\\Scripts\\mt-karaoke-ui.exe" in launcher
    assert "D:\\" not in launcher


def test_portable_build_contract_contains_mutable_roots_and_ffmpeg_gate():
    script = (PROJECT_ROOT / "build-portable.bat").read_text(encoding="utf-8")
    assert "portable.flag" in script
    assert "\\data" in script
    assert "\\logs" in script
    assert "\\config" in script
    assert "MT_FFMPEG_ROOT" in script
    assert "bin\\ffmpeg.exe" in script
    assert "installer\\package.ps1" in script


def test_pyinstaller_spec_bundles_required_read_only_assets():
    spec = (PROJECT_ROOT / "packaging" / "MT-Karaoke-Studio.spec").read_text(encoding="utf-8")
    for required in ("assets", "migrations", "alembic.ini", "openrouter.env.example"):
        assert required in spec
    assert "console=False" in spec


def test_zip_installer_has_location_relative_batch_entrypoints():
    install = (PROJECT_ROOT / "install.bat").read_text(encoding="utf-8")
    run = (PROJECT_ROOT / "run.bat").read_text(encoding="utf-8")
    installer = (PROJECT_ROOT / "installer" / "install.ps1").read_text(encoding="utf-8")
    launcher = (PROJECT_ROOT / "installer" / "run.ps1").read_text(encoding="utf-8")
    packager = (PROJECT_ROOT / "installer" / "package.ps1").read_text(encoding="utf-8")

    assert "%~dp0installer\\install.ps1" in install
    assert "%~dp0installer\\run.ps1" in run
    assert "LOCALAPPDATA" in installer
    assert "MT_KARAOKE_INSTALL_ROOT" in installer
    assert "portable.flag" in installer
    assert "install-manifest.json" in installer
    assert "--smoke-test" in installer
    assert "models\\faster-whisper" in installer
    assert "models--Systran--faster-whisper-base" in packager
    assert "Run install.bat first" in launcher
    assert ".venv\\Scripts\\mt-karaoke-ui.exe" in launcher


@pytest.mark.skipif(sys.platform != "win32", reason="Windows installer contract")
def test_installer_copies_payload_and_removes_portable_mode(tmp_path: Path):
    package = tmp_path / "extracted"
    shutil.copytree(PROJECT_ROOT / "installer", package / "installer")
    shutil.copy2(PROJECT_ROOT / "install.bat", package / "install.bat")
    payload = package / "payload"
    payload.mkdir()
    (payload / "MT-Karaoke-Studio.exe").write_bytes(b"fixture")
    (payload / "portable.flag").touch()
    bundled_model = (
        payload
        / "models"
        / "faster-whisper"
        / "models--Systran--faster-whisper-base"
        / "snapshots"
        / "fixture"
    )
    bundled_model.mkdir(parents=True)
    (bundled_model / "config.json").write_text("{}", encoding="utf-8")
    (bundled_model / "model.bin").write_bytes(b"base")
    (bundled_model / "tokenizer.json").write_text("{}", encoding="utf-8")
    install_root = tmp_path / "installed app"
    environment = os.environ.copy()
    environment["MT_KARAOKE_INSTALL_ROOT"] = str(install_root)
    environment["MT_KARAOKE_SKIP_SMOKE_TEST"] = "1"

    result = subprocess.run(
        ["cmd.exe", "/c", "call", str(package / "install.bat")],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert (install_root / "MT-Karaoke-Studio.exe").read_bytes() == b"fixture"
    assert not (install_root / "portable.flag").exists()
    assert (install_root / "install-manifest.json").is_file()
    assert (
        install_root
        / "models"
        / "faster-whisper"
        / "models--Systran--faster-whisper-base"
        / "snapshots"
        / "fixture"
        / "model.bin"
    ).read_bytes() == b"base"

    preserved_model = install_root / "models" / "faster-whisper" / "custom-model"
    preserved_model.mkdir()
    (preserved_model / "keep.txt").write_text("keep", encoding="utf-8")
    result = subprocess.run(
        ["cmd.exe", "/c", "call", str(package / "install.bat")],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert (install_root / "models" / "faster-whisper" / "custom-model" / "keep.txt").read_text(encoding="utf-8") == "keep"
