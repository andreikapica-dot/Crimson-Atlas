$ErrorActionPreference = "SilentlyContinue"

# Clean up any leftover processes
Stop-Process -Name "Crimson Atlas" -Force
Stop-Process -Name "CrimsonAtlasService" -Force
Start-Sleep -Seconds 3

# Run smoke test
$env:CRIMSON_ATLAS_SMOKE_TEST = "1"
$p = Start-Process -FilePath "D:\Projects\CrimsonDesertMap\release\artifacts\win-unpacked\Crimson Atlas.exe" -WindowStyle Hidden -Wait -PassThru
$env:CRIMSON_ATLAS_SMOKE_TEST = ""
Write-Host ("win-unpacked smoke test: exit=" + $p.ExitCode)

# Verify artifacts
Write-Host ""
Write-Host "=== Artifacts ==="
Get-ChildItem "D:\Projects\CrimsonDesertMap\release\artifacts" -File | Select-Object Name, Length | Format-Table -AutoSize

Write-Host "=== SHA256SUMS ==="
Get-Content "D:\Projects\CrimsonDesertMap\release\artifacts\SHA256SUMS.txt"

Write-Host ""
Write-Host "=== Backend info ==="
$backendExe = Get-Item "D:\Projects\CrimsonDesertMap\release\backend-dist\CrimsonAtlasService\CrimsonAtlasService.exe"
Write-Host ("  Path: " + $backendExe.FullName)
Write-Host ("  Size: " + $backendExe.Length + " bytes")
$hash = Get-FileHash -Algorithm SHA256 $backendExe.FullName
Write-Host ("  SHA-256: " + $hash.Hash)
