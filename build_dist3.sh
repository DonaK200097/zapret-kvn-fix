#!/bin/bash
# Build XrayFluent to dist3 with data preservation
set -e

cd "G:/bin/Xray-windows-64"

# Kill processes
wmic process where "name='XrayFluent.exe'" call terminate 2>/dev/null || true
wmic process where "name='tun2socks.exe'" call terminate 2>/dev/null || true
wmic process where "name='xray.exe'" call terminate 2>/dev/null || true
sleep 3

# Backup data from dist3 if exists
if [ -d "dist3/XrayFluent/data" ]; then
    rm -rf dist3/_data_backup 2>/dev/null
    cp -r dist3/XrayFluent/data dist3/_data_backup
    echo "Backed up dist3 data"
fi

# Clean and build
rm -rf dist3/XrayFluent 2>/dev/null
.venv/Scripts/python -m PyInstaller main.py --name XrayFluent --distpath dist3 \
    --noconfirm --console --onedir --uac-admin --manifest uac_admin.manifest \
    --hidden-import win32comext --hidden-import win32comext.shell --hidden-import win32comext.shell.shellcon

# Copy core
cp -r core dist3/XrayFluent/

# Restore data
if [ -d "dist3/_data_backup" ]; then
    cp -r dist3/_data_backup dist3/XrayFluent/data
    echo "Restored dist3 data"
elif [ -d "dist/_data_backup" ]; then
    cp -r dist/_data_backup dist3/XrayFluent/data
    echo "Copied data from dist backup"
fi

ls dist3/XrayFluent/XrayFluent.exe && echo "BUILD OK"
