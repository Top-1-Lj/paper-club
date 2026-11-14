param([ValidateRange(1024, 65535)][int]$Port = 8000)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$DemoPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $DemoPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $DemoPython -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $DemoPython manage.py migrate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $DemoPython manage.py seed_demo
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $DemoPython manage.py import_papers
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Paper Club: http://127.0.0.1:$Port"
Write-Host 'Demo accounts: lin / chen; initial password: PaperClub2026!'
& $DemoPython manage.py runserver "127.0.0.1:$Port"
exit $LASTEXITCODE
