"""Self-update: check GitHub releases, download, extract, restart."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request

from .http_utils import build_opener, urlopen

from PyQt6.QtCore import QThread, pyqtSignal

from .constants import APP_VERSION, BASE_DIR

GITHUB_REPO = "youtubediscord/zapret-kvn"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
USER_AGENT = f"ZapretKVN/{APP_VERSION}"


@dataclass(slots=True)
class AppUpdate:
    version: str
    tag: str
    download_url: str
    size: int
    notes: str


def _parse_version(v: str) -> tuple[int, ...]:
    clean = v.lstrip("v").split("-")[0]
    return tuple(int(x) for x in clean.split(".") if x.isdigit())


class UpdateChecker(QThread):
    """Check GitHub for a newer release."""

    result = pyqtSignal(object)  # AppUpdate | None
    error = pyqtSignal(str)

    def run(self) -> None:
        try:
            req = Request(GITHUB_API, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())

            tag = data.get("tag_name", "")
            remote = _parse_version(tag)
            local = _parse_version(APP_VERSION)

            if remote <= local:
                self.result.emit(None)
                return

            asset = None
            for a in data.get("assets", []):
                name = a.get("name", "").lower()
                if name.endswith(".zip") and "windows" in name and "x64" in name:
                    asset = a
                    break

            if not asset:
                self.error.emit(f"Релиз {tag} найден, но отсутствует Windows zip-архив")
                self.result.emit(None)
                return

            self.result.emit(AppUpdate(
                version=tag.lstrip("v"),
                tag=tag,
                download_url=asset["browser_download_url"],
                size=asset.get("size", 0),
                notes=data.get("body", ""),
            ))
        except Exception as exc:
            self.error.emit(str(exc))
            self.result.emit(None)


_log = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT = 30  # seconds — per socket operation (connect + each read)


class UpdateDownloader(QThread):
    """Download and extract update, then launch restart script."""

    progress = pyqtSignal(int)       # percent 0-100
    status = pyqtSignal(str)         # human-readable status message
    finished_ok = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, update: AppUpdate, proxy_url: str | None = None, parent=None):
        super().__init__(parent)
        self._update = update
        self._proxy_url = proxy_url

    # ── download helper ─────────────────────────────────────────

    def _download(self, zip_path: Path, proxy_url: str | None) -> None:
        """Download update zip. Raises on failure/stall.

        Socket timeout (_DOWNLOAD_TIMEOUT) applies to each read() call,
        so a dead proxy will raise within 30 s instead of hanging forever.
        """
        req = Request(self._update.download_url, headers={"User-Agent": USER_AGENT})
        if proxy_url:
            handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            opener = build_opener(handler)
        else:
            opener = build_opener()

        with opener.open(req, timeout=_DOWNLOAD_TIMEOUT) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            with open(zip_path, "wb") as f:
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        if downloaded == 0:
                            raise TimeoutError("Сервер не отдаёт данные")
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        self.progress.emit(int(downloaded * 100 / total))

    # ── main thread entry ───────────────────────────────────────

    def run(self) -> None:
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix="zapretkvn_update_"))
            zip_path = tmp_dir / "update.zip"

            downloaded_ok = False

            # Attempt 1: through proxy (if available)
            if self._proxy_url:
                self.status.emit("Загрузка через прокси...")
                try:
                    self._download(zip_path, self._proxy_url)
                    downloaded_ok = True
                except Exception as exc:
                    _log.warning("Proxy download failed: %s", exc)
                    self.status.emit(
                        "Прокси-сервер недоступен, пробую напрямую..."
                    )
                    self.progress.emit(0)
                    # clean partial file
                    if zip_path.exists():
                        zip_path.unlink()

            # Attempt 2: direct (no proxy)
            if not downloaded_ok:
                self.status.emit("Загрузка напрямую...")
                try:
                    self._download(zip_path, None)
                    downloaded_ok = True
                except Exception as exc:
                    _log.warning("Direct download failed: %s", exc)

            if not downloaded_ok:
                msg = (
                    "Не удалось скачать обновление.\n"
                    "Переключитесь на рабочий сервер и попробуйте снова."
                )
                if self._proxy_url:
                    msg = (
                        "Не удалось скачать обновление ни через прокси, ни напрямую.\n"
                        "Переключитесь на рабочий сервер и попробуйте снова."
                    )
                self.error.emit(msg)
                # cleanup
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return

            self.progress.emit(100)
            self.status.emit("Распаковка...")

            # Extract
            extract_dir = tmp_dir / "extracted"
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            # Write restart script
            exe_name = "ZapretKVN.exe"
            app_dir = str(BASE_DIR)
            src_dir = str(extract_dir)
            script = tmp_dir / "_update.bat"
            script.write_text(
                "@echo off\r\n"
                "echo Updating zapret kvn...\r\n"
                "timeout /t 2 /nobreak >nul\r\n"
                f'taskkill /F /IM {exe_name} 2>nul\r\n'
                "timeout /t 1 /nobreak >nul\r\n"
                f'xcopy /E /Y /Q "{src_dir}\\*" "{app_dir}\\"\r\n'
                "echo Update complete. Restarting...\r\n"
                f'start "" "{app_dir}\\{exe_name}"\r\n'
                f'rmdir /S /Q "{str(tmp_dir)}"\r\n',
                encoding="ascii",
            )

            # Launch script and exit
            subprocess.Popen(
                ["cmd", "/c", str(script)],
                creationflags=0x08000000,
                close_fds=True,
            )

            self.finished_ok.emit()

        except Exception as exc:
            self.error.emit(str(exc))
