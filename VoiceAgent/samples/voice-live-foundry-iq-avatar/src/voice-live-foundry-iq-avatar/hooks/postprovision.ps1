#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python provision_kb.py --require-azd-env
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
