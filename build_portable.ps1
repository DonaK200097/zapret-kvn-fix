$ErrorActionPreference = "Stop"

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment not found. Run setup.bat first."
    exit 1
}

& $venvPython -m PyInstaller main.py `
    --name XrayFluent `
    --noconfirm `
    --clean `
    --noconsole `
    --onedir `
    --uac-admin `
    --manifest uac_admin.manifest `
    --hidden-import win32comext `
    --hidden-import win32comext.shell `
    --hidden-import win32comext.shell.shellcon

Copy-Item -Path ".\core" -Destination ".\dist\XrayFluent\core" -Recurse -Force

$zipPath = ".\dist\XrayFluent-portable.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Compress-Archive -Path ".\dist\XrayFluent\*" -DestinationPath $zipPath
Write-Host "Portable build created: $zipPath"
