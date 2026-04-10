$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$dbPath = Join-Path $projectRoot "db.sqlite3"
$journalPath = Join-Path $projectRoot "db.sqlite3-journal"
$walPath = Join-Path $projectRoot "db.sqlite3-wal"
$shmPath = Join-Path $projectRoot "db.sqlite3-shm"

if (-not (Test-Path $python)) {
    throw "Python interpreter not found: $python"
}

$projectPythonProcesses = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "python.exe" -and
        $_.ExecutablePath -eq $python
    }

foreach ($proc in $projectPythonProcesses) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Milliseconds 500

foreach ($path in @($journalPath, $walPath, $shmPath)) {
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $dbPath)) {
    throw "Database file not found: $dbPath"
}

$probe = @"
import sqlite3
from pathlib import Path

db_path = Path(r"$dbPath")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")
cur.execute("PRAGMA foreign_keys=ON;")
cur.execute("CREATE TABLE IF NOT EXISTS __startup_probe (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
cur.execute("INSERT INTO __startup_probe DEFAULT VALUES")
conn.commit()
conn.close()
print("SQLite write probe OK")
"@

$probe | & $python -

Write-Host "Starting Django on http://127.0.0.1:8000 ..."
& $python manage.py runserver 127.0.0.1:8000 --noreload
