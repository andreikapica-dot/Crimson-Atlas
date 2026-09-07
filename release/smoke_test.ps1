$env:CRIMSON_ATLAS_SMOKE_TEST = "1"
$p = Start-Process -FilePath "D:\Projects\CrimsonDesertMap\release\artifacts\win-unpacked\Crimson Atlas.exe" -WindowStyle Hidden -Wait -PassThru
$env:CRIMSON_ATLAS_SMOKE_TEST = ""
Write-Host ("win-unpacked smoke: exit=" + $p.ExitCode)
