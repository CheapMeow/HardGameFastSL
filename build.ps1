param(
    [string]$Python = $env:HARDGAMEFASTSL_PYTHON
)

$ErrorActionPreference = "Stop"

if (-not $Python) {
    throw "Python interpreter not specified: pass -Python or set HARDGAMEFASTSL_PYTHON"
}

Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
    if ($LASTEXITCODE) { throw "venv creation failed" }
}
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE) { throw "pip install failed" }

& $venvPython -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name HardGameFastSL `
    --distpath dist --workpath build --specpath build `
    main.py
if ($LASTEXITCODE) { throw "PyInstaller failed" }

Copy-Item config.json dist\config.json -Force
