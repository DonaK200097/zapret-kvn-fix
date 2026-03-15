"""
Build XrayFluent portable exe via PyInstaller.

Usage:  python build.py          — full build (clean + compile + pack zip)
        python build.py --no-zip — skip zip creation
        python build.py --clean  — only wipe previous build artefacts

Requires .venv created by setup.bat (or manually).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
VENV_PIP = VENV_DIR / "Scripts" / "pip.exe"

DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
APP_DIR = DIST_DIR / "XrayFluent"
ZIP_PATH = DIST_DIR / "XrayFluent-portable.zip"

MANIFEST = ROOT / "uac_admin.manifest"
CORE_DIR = ROOT / "core"

APP_NAME = "XrayFluent"
DEBUG_LAUNCHER_NAME = "Run XrayFluent Debug.bat"


def _print(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def _run(cmd: list[str], **kwargs) -> None:
    _print(f"> {' '.join(cmd)}")
    subprocess.run(cmd, check=True, **kwargs)


def write_debug_launcher() -> None:
    launcher_path = APP_DIR / DEBUG_LAUNCHER_NAME
    launcher_path.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "set XRAY_FLUENT_SHOW_CONSOLE=1\r\n"
        "echo Launching Xray Fluent in debug mode...\r\n"
        "echo Startup log: %~dp0data\\logs\\startup.log\r\n"
        "echo.\r\n"
        '"%~dp0XrayFluent.exe" --show-console\r\n'
        "set EXIT_CODE=%ERRORLEVEL%\r\n"
        "echo.\r\n"
        "echo Exit code: %EXIT_CODE%\r\n"
        "echo Startup log: %~dp0data\\logs\\startup.log\r\n"
        "pause\r\n"
        "endlocal\r\n",
        encoding="ascii",
    )
    _print(f"Wrote debug launcher: {launcher_path}")


# ------------------------------------------------------------------
def ensure_venv() -> None:
    if VENV_PYTHON.exists():
        _print(f"venv OK: {VENV_PYTHON}")
        return
    _print("Creating virtual environment ...")
    _run([sys.executable, "-m", "venv", str(VENV_DIR)])
    _run([str(VENV_PIP), "install", "--upgrade", "pip"])
    _run([str(VENV_PIP), "install", "-r", str(ROOT / "requirements.txt")])


def clean() -> None:
    # build/ is purely temporary — safe to nuke
    if BUILD_DIR.exists():
        _print(f"Removing {BUILD_DIR}")
        try:
            shutil.rmtree(BUILD_DIR)
        except PermissionError:
            _print(f"ERROR: Cannot remove {BUILD_DIR} — is XrayFluent.exe still running?")
            _print("Close the app (tray -> Quit) and try again.")
            raise SystemExit(1)

    # dist/XrayFluent/ — remove everything EXCEPT data/ (state, keys, logs)
    if APP_DIR.exists():
        data_dir = APP_DIR / "data"
        for child in APP_DIR.iterdir():
            if child == data_dir:
                _print(f"Keeping {data_dir}")
                continue
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            except PermissionError:
                _print(f"ERROR: Cannot remove {child} — is XrayFluent.exe still running?")
                _print("Close the app (tray -> Quit) and try again.")
                raise SystemExit(1)
        _print(f"Cleaned {APP_DIR} (data/ preserved)")

    spec = ROOT / f"{APP_NAME}.spec"
    if spec.exists():
        spec.unlink()


def build_exe() -> None:
    ensure_venv()

    # Preserve data/ across PyInstaller rebuild (it nukes dist/AppName/)
    data_dir = APP_DIR / "data"
    data_backup = DIST_DIR / "_data_backup"
    if data_dir.exists():
        if data_backup.exists():
            shutil.rmtree(data_backup)
        _print(f"Backing up {data_dir} -> {data_backup}")
        shutil.move(str(data_dir), str(data_backup))

    cmd = [
        str(VENV_PYTHON), "-m", "PyInstaller",
        str(ROOT / "main.py"),
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
        "--console",
        "--onedir",
        "--uac-admin",
        "--manifest", str(MANIFEST),
        # win32comext is needed by qframelesswindow for Mica/DWM effects
        "--hidden-import", "win32comext",
        "--hidden-import", "win32comext.shell",
        "--hidden-import", "win32comext.shell.shellcon",
    ]
    _run(cmd, cwd=str(ROOT))

    # Restore data/
    if data_backup.exists():
        if data_dir.exists():
            shutil.rmtree(data_dir)
        _print(f"Restoring {data_backup} -> {data_dir}")
        shutil.move(str(data_backup), str(data_dir))

    # Copy core/ into dist
    dst_core = APP_DIR / "core"
    if dst_core.exists():
        shutil.rmtree(dst_core)
    _print(f"Copying core -> {dst_core}")
    shutil.copytree(str(CORE_DIR), str(dst_core))

    write_debug_launcher()

    _print(f"Build complete: {APP_DIR / (APP_NAME + '.exe')}")


def pack_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    _print(f"Creating {ZIP_PATH} ...")
    shutil.make_archive(str(ZIP_PATH.with_suffix("")), "zip", str(DIST_DIR), APP_NAME)
    _print(f"Portable archive ready: {ZIP_PATH}")


# ------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Build XrayFluent portable exe")
    parser.add_argument("--no-zip", action="store_true", help="skip zip creation")
    parser.add_argument("--clean", action="store_true", help="only clean build artefacts")
    args = parser.parse_args()

    os.chdir(ROOT)

    if args.clean:
        clean()
        _print("Done.")
        return 0

    clean()
    build_exe()

    if not args.no_zip:
        pack_zip()

    _print("All done!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
