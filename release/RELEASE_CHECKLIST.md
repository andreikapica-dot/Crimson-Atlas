# Crimson Atlas release checklist

## Automated gates

- [ ] Frontend tests pass.
- [ ] Frontend production build passes without source maps.
- [ ] Python tests pass.
- [ ] Packaged backend `--self-test` passes without opening or attaching to the game.
- [ ] Packaged desktop `--release-smoke-test` passes without starting the backend.
- [ ] Release audit finds no source files, development folders, or plain Python files.
- [ ] SHA-256 checksums are generated.

## Manual gates before public release

- [ ] Confirm redistribution rights for the Pywel and Abyss map imagery.
- [ ] Confirm redistribution rights and attribution requirements for the marker catalog and icons.
- [ ] Replace or remove any asset whose license cannot be documented.
- [ ] Test install, update, uninstall, portable launch, and saved user data on a clean Windows 11 account.
- [ ] Test game detection, coordinates, map switching, marker editing, Found state, and teleport on the supported game build.
- [ ] Test with the game in borderless and exclusive fullscreen modes.
- [ ] Obtain a Windows code-signing certificate and sign the application and installer.
- [ ] Scan both release executables with Windows Security and a multi-engine service.
- [ ] Publish a privacy statement, supported game version, known limitations, and a contact method.

An unsigned build is suitable only for a small private beta. Windows may show an unknown-publisher warning until signing is configured.
