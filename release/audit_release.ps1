$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifacts = Join-Path $PSScriptRoot "artifacts"
$unpacked = Join-Path $artifacts "win-unpacked"
$asarPath = Join-Path $unpacked "resources\app.asar"
$backendPath = Join-Path $unpacked "resources\backend\CrimsonAtlasService"
$asarTool = Join-Path $projectRoot "frontend\node_modules\.bin\asar.cmd"

foreach ($required in @($asarPath, $backendPath, $asarTool)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Release audit cannot find: $required"
    }
}

$asarEntries = & $asarTool list $asarPath
if ($LASTEXITCODE -ne 0) { throw "Could not inspect app.asar" }

$forbidden = @("node_modules", ".venv", "tests", "work", "diagnostics", ".git", ".py", ".ts", ".map")
foreach ($fragment in $forbidden) {
    $matches = $asarEntries | Where-Object { $_ -like "*$fragment*" }
    if ($matches) { throw "Forbidden release content '$fragment': $($matches -join ', ')" }
}

$plainPython = Get-ChildItem -LiteralPath $backendPath -Recurse -File | Where-Object { $_.Extension -in @(".py", ".pyc") }
if ($plainPython) { throw "Plain Python files leaked into the backend: $($plainPython.FullName -join ', ')" }

$installer = Get-ChildItem -LiteralPath $artifacts -File | Where-Object { $_.Name -like "*-Setup.exe" }
$portable = Get-ChildItem -LiteralPath $artifacts -File | Where-Object { $_.Name -like "*-Portable.exe" }
if (-not $installer -or -not $portable) { throw "Installer or portable artifact is missing" }

$hashes = Get-ChildItem -LiteralPath $artifacts -File -Filter "*.exe" | Get-FileHash -Algorithm SHA256
$hashLines = $hashes | ForEach-Object { "$($_.Hash.ToLower())  $([IO.Path]::GetFileName($_.Path))" }
Set-Content -LiteralPath (Join-Path $artifacts "SHA256SUMS.txt") -Value $hashLines -Encoding utf8

Write-Host "Release audit passed."
$hashLines | ForEach-Object { Write-Host $_ }
