"""Minimal winws2 (zapret2) process manager — preset-based, no orchestrator."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

from .constants import BASE_DIR

log = logging.getLogger(__name__)

ZAPRET_DIR = BASE_DIR / "zapret"
WINWS2_EXE = ZAPRET_DIR / "exe" / "winws2.exe"
PRESETS_DIR = ZAPRET_DIR / "presets"

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class ZapretManager(QObject):
    """Start / stop winws2.exe with a preset file."""

    started = pyqtSignal()
    stopped = pyqtSignal()
    error = pyqtSignal(str)
    log_line = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(3000)
        self._health_timer.timeout.connect(self._check_health)

    # ── public API ──────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.state() == QProcess.ProcessState.Running

    @staticmethod
    def list_presets() -> list[str]:
        """Return sorted list of available preset names (without .txt)."""
        if not PRESETS_DIR.is_dir():
            return []
        return sorted(
            p.stem for p in PRESETS_DIR.iterdir()
            if p.suffix == ".txt" and not p.name.startswith("_")
        )

    @staticmethod
    def preset_path(name: str) -> Path:
        return PRESETS_DIR / f"{name}.txt"

    @staticmethod
    def _parse_preset_args(preset: Path) -> list[str]:
        """Read preset file and return list of arguments (skip comments/blanks)."""
        args: list[str] = []
        text = preset.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                args.append(stripped)
        return args

    def start(self, preset_name: str) -> None:
        if self.running:
            self.stop()

        exe = WINWS2_EXE
        if not exe.exists():
            self.error.emit(f"winws2.exe не найден: {exe}")
            return

        preset = self.preset_path(preset_name)
        if not preset.exists():
            self.error.emit(f"Пресет не найден: {preset}")
            return

        # Parse preset and pass args directly (winws2 @file can't handle spaces in path)
        args = self._parse_preset_args(preset)
        if not args:
            self.error.emit(f"Пресет пустой: {preset_name}")
            return

        self._process = QProcess(self)
        self._process.setProgram(str(exe))
        self._process.setArguments(args)
        self._process.setWorkingDirectory(str(ZAPRET_DIR))
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)

        log.info("zapret start: %s [%s] (%d args)", exe.name, preset_name, len(args))
        self.log_line.emit(f"[zapret] Запуск: {preset_name} ({len(args)} аргументов)")
        self._process.start()

        if not self._process.waitForStarted(5000):
            self.error.emit("Не удалось запустить winws2.exe")
            self._process = None
            return

        self._health_timer.start()
        self.started.emit()

    def stop(self) -> None:
        self._health_timer.stop()
        if self._process is None:
            return

        if self._process.state() == QProcess.ProcessState.Running:
            log.info("zapret stop")
            self._process.kill()
            self._process.waitForFinished(5000)

        self._process = None
        self.stopped.emit()

    # ── internals ───────────────────────────────────────────────

    def _drain_output(self) -> list[str]:
        """Read any remaining stdout/stderr from the process."""
        lines: list[str] = []
        if self._process is None:
            return lines
        for reader in (self._process.readAllStandardOutput,
                       self._process.readAllStandardError):
            data = reader().data()
            if data:
                for line in data.decode("utf-8", errors="replace").splitlines():
                    stripped = line.strip()
                    if stripped:
                        lines.append(stripped)
        return lines

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput().data()
        for line in data.decode("utf-8", errors="replace").splitlines():
            if line.strip():
                self.log_line.emit(f"[zapret] {line.strip()}")

    def _on_stderr(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardError().data()
        for line in data.decode("utf-8", errors="replace").splitlines():
            if line.strip():
                self.log_line.emit(f"[zapret] {line.strip()}")

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._health_timer.stop()

        # Drain any buffered output before dropping the process reference
        remaining = self._drain_output()
        for line in remaining:
            self.log_line.emit(f"[zapret] {line}")

        log.info("zapret finished: code=%d status=%s", exit_code, exit_status.name)

        if exit_code != 0 or exit_status == QProcess.ExitStatus.CrashExit:
            detail = "\n".join(remaining) if remaining else "нет вывода"
            self.log_line.emit(
                f"[zapret] Процесс завершился с кодом {exit_code}"
            )
            self.error.emit(
                f"winws2 завершился с кодом {exit_code}\n{detail}"
            )

        self._process = None
        self.stopped.emit()

    def _check_health(self) -> None:
        if not self.running:
            self._health_timer.stop()
            self.stopped.emit()
