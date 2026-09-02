# Building Crimson Atlas for Windows

Run from PowerShell in the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\release\build_release.ps1 -InstallDependencies
```

Later builds can omit `-InstallDependencies` when the locked build tools are already installed.

Outputs are written to `release/artifacts/`:

- `Crimson Atlas-*-Setup.exe` - per-user installer with uninstall support.
- `Crimson Atlas-*-Portable.exe` - portable single-file launcher.
- `win-unpacked/` - unpacked build used by automated smoke tests.
- `SHA256SUMS.txt` - checksums for release verification.

The shipped frontend is stored in Electron's ASAR archive. The memory engine is compiled to native Python extensions and the service is frozen into a standalone directory. This prevents casual access to the original source tree, but no client-side packaging method can make local code impossible to reverse engineer.

Do not publish the build until every manual item in `RELEASE_CHECKLIST.md` is complete.
