$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifacts = Join-Path $PSScriptRoot "artifacts"
$unpacked = Join-Path $artifacts "win-unpacked"
$readme = Join-Path $PSScriptRoot "NEXUS_README.txt"
$version = (Get-Content -LiteralPath (Join-Path $projectRoot "package.json") -Raw | ConvertFrom-Json).version
$archive = Join-Path $artifacts "Crimson-Atlas-$version-Nexus.zip"

foreach ($required in @($unpacked, $readme)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Nexus package input is missing: $required" }
}
if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }

# Upload the already-unpacked application. This avoids the nested NSIS/7z
# payload that Nexus previously mistook for an unusual DLL archive.
Compress-Archive -Path (Join-Path $unpacked "*"), $readme -DestinationPath $archive -CompressionLevel Optimal
$hash = Get-FileHash -LiteralPath $archive -Algorithm SHA256
Add-Content -LiteralPath (Join-Path $artifacts "SHA256SUMS.txt") -Value "$($hash.Hash.ToLower())  $($hash.Path | Split-Path -Leaf)" -Encoding utf8
Write-Host "Nexus archive: $archive"
Write-Host "SHA256: $($hash.Hash)"
