from __future__ import annotations

import os
import shlex
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

if sys.platform == "win32":
    import winreg


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _run_command(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(stderr or f"Command exited with code {result.returncode}")


def _run_schtasks(args: list[str]) -> None:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    schtasks = str(Path(system_root) / "System32" / "schtasks.exe")
    _run_command([schtasks, *args])


def _run_powershell(script: str) -> None:
    powershell = os.environ.get("WINDIR", r"C:\Windows") + r"\System32\WindowsPowerShell\v1.0\powershell.exe"
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(stderr or f"PowerShell exited with code {result.returncode}")


def _remove_legacy_run_key(app_name: str) -> None:
    if sys.platform != "win32":
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        pass


def _split_command(command: str) -> tuple[str, str]:
    parts = shlex.split(command, posix=False)
    if not parts:
        raise ValueError("Empty startup command")
    exe = parts[0].strip('"')
    args = subprocess.list2cmdline(parts[1:]) if len(parts) > 1 else ""
    return exe, args


def _task_xml(task_name: str, command: str, delay_seconds: int = 15) -> str:
    exe, args = _split_command(command)
    ns = "http://schemas.microsoft.com/windows/2004/02/mit/task"
    ET.register_namespace("", ns)

    def tag(name: str) -> str:
        return f"{{{ns}}}{name}"

    task = ET.Element(tag("Task"), version="1.4")
    reg = ET.SubElement(task, tag("RegistrationInfo"))
    ET.SubElement(reg, tag("Date")).text = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ET.SubElement(reg, tag("Author")).text = task_name

    triggers = ET.SubElement(task, tag("Triggers"))
    logon = ET.SubElement(triggers, tag("LogonTrigger"))
    ET.SubElement(logon, tag("Enabled")).text = "true"
    ET.SubElement(logon, tag("Delay")).text = f"PT{delay_seconds}S"

    principals = ET.SubElement(task, tag("Principals"))
    principal = ET.SubElement(principals, tag("Principal"), id="Author")
    ET.SubElement(principal, tag("UserId")).text = os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")
    ET.SubElement(principal, tag("LogonType")).text = "InteractiveToken"
    ET.SubElement(principal, tag("RunLevel")).text = "HighestAvailable"

    settings = ET.SubElement(task, tag("Settings"))
    ET.SubElement(settings, tag("MultipleInstancesPolicy")).text = "IgnoreNew"
    ET.SubElement(settings, tag("DisallowStartIfOnBatteries")).text = "false"
    ET.SubElement(settings, tag("StopIfGoingOnBatteries")).text = "false"
    ET.SubElement(settings, tag("AllowHardTerminate")).text = "true"
    ET.SubElement(settings, tag("StartWhenAvailable")).text = "true"
    ET.SubElement(settings, tag("RunOnlyIfNetworkAvailable")).text = "false"
    ET.SubElement(settings, tag("Enabled")).text = "true"
    ET.SubElement(settings, tag("Hidden")).text = "false"
    ET.SubElement(settings, tag("WakeToRun")).text = "false"
    ET.SubElement(settings, tag("ExecutionTimeLimit")).text = "PT0S"
    ET.SubElement(settings, tag("Priority")).text = "7"

    actions = ET.SubElement(task, tag("Actions"), Context="Author")
    exec_action = ET.SubElement(actions, tag("Exec"))
    ET.SubElement(exec_action, tag("Command")).text = exe
    if args:
        ET.SubElement(exec_action, tag("Arguments")).text = args

    return ET.tostring(task, encoding="unicode")


def set_startup_enabled(app_name: str, enabled: bool, command: str) -> None:
    if sys.platform != "win32":
        return

    _remove_legacy_run_key(app_name)
    task_name = app_name
    if enabled:
        with tempfile.TemporaryDirectory(prefix="zapretkvn_task_") as tmp:
            xml_path = Path(tmp) / "task.xml"
            xml_path.write_text(_task_xml(task_name, command, delay_seconds=15), encoding="utf-8")
            _run_schtasks(["/Create", "/F", "/TN", task_name, "/XML", str(xml_path)])
    else:
        _run_schtasks(["/Delete", "/F", "/TN", task_name])


def build_startup_command(start_in_tray: bool = True) -> str:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return f'"{exe}" --tray' if start_in_tray else f'"{exe}"'

    base_dir = Path(__file__).resolve().parents[1]
    script = base_dir / "main.py"
    venv_pythonw = base_dir / ".venv" / "Scripts" / "pythonw.exe"
    python_exe = venv_pythonw if venv_pythonw.exists() else Path(sys.executable).resolve()
    return f'"{python_exe}" "{script}" --tray' if start_in_tray else f'"{python_exe}" "{script}"'
