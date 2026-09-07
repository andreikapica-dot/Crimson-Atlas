# Crimson Atlas 0.1.0-beta.4

## Исправления последней тестовой сборки

- одиночные метки больше не исчезают после распада кластеров на максимальном масштабе;
- каталог обновлён из актуальной выгрузки TH.GL, удалены дубли и ошибочные низковысотные точки Бездны;
- служебные имена локализации вида `@hjeglx` заменены понятными названиями предметов;
- подтверждённая торговая точка исправлена с «Магазин» на «Торговый пост»;
- portable-версия сохраняет среду встроенной службы на всё время сеанса, поэтому поздняя загрузка сетевого модуля Crimson Route больше не теряет `base_library.zip`;
- если Local API Crimson Route выключен, интерфейс теперь показывает понятную инструкцию.
- возвращены детальные изображения островов Бездны в уменьшенном масштабе без прежнего двойного увеличения;
- при наведении на одиночную метку показываются её точное название, категория и координаты;
- `Ctrl+Shift+A` теперь скрывает и возвращает основное окно;
- добавлено отдельное безрамочное окно навигации, которое автоматически открывается после построения маршрута и переключается сочетанием `Ctrl+Shift+N`.

## Release Notes

- Added optional Crimson Route integration.
- Routes can be built directly to Atlas markers.
- Added primary and alternative route rendering.
- Added automatic route recalculation while moving.
- Improved route responsiveness with faster rerouting.
- Added visual route trimming as the player progresses.
- Added destination arrival detection.
- Added route clearing controls.
- Markers without known Y coordinates can still be used for navigation.
- Atlas now sends an explicit player start position to Crimson Route,
  preventing conflicts with live player tracking.
- Various stability improvements.
- Unified position source selection across game builds: Physics Hook is
  now always attempted first; Static XYZ is a fallback only. Teleport is
  available whenever the Physics Hook installs successfully, regardless of
  whether Static XYZ is also present.
- Added `select_position_source()` to `PlayerPositionReader`.
- Added `has_static_xyz()` helper for diagnostics.
- Fixed normal Electron startup failure caused by `ELECTRON_RUN_AS_NODE=1`
  in the environment. Launch scripts (`Start Crimson Atlas.bat` and
  `build_release.ps1` smoke test) now explicitly clear this variable so the
  Electron runtime initializes correctly and `require("electron")` resolves.

## Limitations

- This is an unsigned build. Windows may show an unknown-publisher warning
  until a code-signing certificate is configured.
- Live memory/teleport/Crimson Route have NOT been verified in-game. They
  have only been validated via the packaged backend `--self-test` and unit
  tests with mock process objects.

## Artifacts

- `Crimson Atlas-0.1.0-beta.4-x64-Setup.exe` — per-user installer with
  uninstall support.
- `Crimson Atlas-0.1.0-beta.4-x64-Portable.exe` — single-file portable
  launcher.
- `SHA256SUMS.txt` — checksums for release verification.

## Checksums

```
8711eb9e30a92df1ef7c3e7bbd33f2a7943962a79c15cf706b4d6e7cd15ade33  Crimson Atlas-0.1.0-beta.4-x64-Portable.exe
98decf0c038da8dcb6d362f80afebc27d4a04a76284ca24b51cb03717d3ce30e  Crimson Atlas-0.1.0-beta.4-x64-Setup.exe
```

Backend (`CrimsonAtlasService.exe`): SHA-256 `9DEE6ED86A3A4B40AD22460510CD53D7494BBEA250D49A867E89C7042086CBE9`
