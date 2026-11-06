#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

# Use Microsoft's documented Windows x64 installer and verify its signature.
$installerPath = Join-Path ([System.IO.Path]::GetTempPath()) ("azure-cli-" + [guid]::NewGuid().ToString('N') + '.msi')
Write-Host 'Downloading the official Microsoft Azure CLI installer...'
Invoke-WebRequest -Uri 'https://aka.ms/installazurecliwindowsx64' -OutFile $installerPath
$signature = Get-AuthenticodeSignature -LiteralPath $installerPath
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|,\s*)CN=Microsoft Corporation(,|$)') {
    throw 'Installer signature validation failed. Installation was not started.'
}

Write-Host 'Installing Azure CLI...'
$installation = Start-Process -FilePath "$env:SystemRoot\System32\msiexec.exe" -ArgumentList @('/i', ('"' + $installerPath + '"'), '/quiet', '/norestart') -Wait -PassThru -WindowStyle Hidden
if ($installation.ExitCode -notin @(0, 3010)) {
    throw "Azure CLI installer failed with exit code $($installation.ExitCode). Installer retained at $installerPath"
}

$cliPath = 'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd'
if (-not (Test-Path -LiteralPath $cliPath)) {
    $cliPath = 'C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd'
}
if (-not (Test-Path -LiteralPath $cliPath)) {
    throw 'Installer finished but az.cmd was not found. Open a new terminal and run az version.'
}
& $cliPath version
if ($LASTEXITCODE -ne 0) { throw 'Azure CLI installed but its version check failed.' }
Write-Host 'Installation verified. Open a normal PowerShell window and run az login.'
Write-Host "Installer retained at $installerPath"
