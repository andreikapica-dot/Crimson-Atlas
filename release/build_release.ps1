param(
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$npm = "npm.cmd"
$builder = Join-Path $projectRoot "frontend\node_modules\.bin\electron-builder.cmd"

function Remove-ReleaseDirectory([string]$Path) {
    $releaseRoot = (Resolve-Path $PSScriptRoot).Path
    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($releaseRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside release/: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) { Remove-Item -LiteralPath $fullPath -Recurse -Force }
}

if (-not (Test-Path -LiteralPath $python)) { throw "Run Setup Crimson Atlas.bat first." }
Set-Location $projectRoot

if ($InstallDependencies) {
    & $python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw "Python build dependency installation failed" }
    & $npm install --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed" }
}

foreach ($path in @("release\artifacts", "release\backend-dist", "release\backend-build")) {
    Remove-ReleaseDirectory (Join-Path $projectRoot $path)
}

& $python release\create_icon.py
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed" }
& $npm --prefix frontend test -- --run
if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed" }
& $npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Python tests failed" }

& $python release\build_backend.py
if ($LASTEXITCODE -ne 0) { throw "Native backend staging failed" }
$backendStage = Join-Path $projectRoot "release\backend-stage"
$hiddenImports = @(
    "ctypes.wintypes",
    "memory.aob",
    "memory.hooks",
    "memory.player_reader",
    "memory.process",
    "memory.scanner",
    "memory.signatures",
    "memory.state",
    "memory.teleport",
    "memory.types"
)
$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm", "--clean", "--onedir", "--console",
    "--name", "CrimsonAtlasService",
    "--distpath", (Join-Path $projectRoot "release\backend-dist"),
    "--workpath", (Join-Path $projectRoot "release\backend-build"),
    "--specpath", (Join-Path $projectRoot "release"),
    "--paths", $backendStage,
    "--collect-submodules", "pymem",
    "--exclude-module", "tkinter",
    "--exclude-module", "pytest"
)
foreach ($module in $hiddenImports) { $pyInstallerArgs += @("--hidden-import", $module) }
$pyInstallerArgs += "service_entry.py"
Push-Location $backendStage
try {
    & $python @pyInstallerArgs
    if ($LASTEXITCODE -ne 0) { throw "Backend packaging failed" }
}
finally {
    Pop-Location
}
& "release\backend-dist\CrimsonAtlasService\CrimsonAtlasService.exe" --self-test
if ($LASTEXITCODE -ne 0) { throw "Packaged backend self-test failed" }

if (-not (Test-Path -LiteralPath $builder)) { throw "electron-builder is not installed in frontend/node_modules" }
& $builder --projectDir $projectRoot --win nsis portable --x64
if ($LASTEXITCODE -ne 0) { throw "Windows package build failed" }
$builderDebug = Join-Path $projectRoot "release\artifacts\builder-debug.yml"
if (Test-Path -LiteralPath $builderDebug) { Remove-Item -LiteralPath $builderDebug -Force }

$smokeExe = Join-Path $projectRoot "release\artifacts\win-unpacked\Crimson Atlas.exe"
$smokeProcess = Start-Process -FilePath $smokeExe -ArgumentList "--release-smoke-test" -WindowStyle Hidden -Wait -PassThru
if ($smokeProcess.ExitCode -ne 0) { throw "Desktop release smoke test failed" }

& (Join-Path $PSScriptRoot "audit_release.ps1")
if ($LASTEXITCODE -ne 0) { throw "Release audit failed" }
Write-Host "Crimson Atlas release build completed."
