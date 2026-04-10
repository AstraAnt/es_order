$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

$projectPythonProcesses = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "python.exe" -and
        $_.ExecutablePath -eq $python
    }

if (-not $projectPythonProcesses) {
    Write-Host "No project Python processes found."
    exit 0
}

foreach ($proc in $projectPythonProcesses) {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "Project Python processes stopped."
