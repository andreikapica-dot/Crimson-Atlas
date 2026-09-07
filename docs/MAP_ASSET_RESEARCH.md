# Map Asset Research — Crimson Atlas Phase 4

## Goal
Determine whether a legally usable, redistributable base map for Crimson Desert can be obtained for local/offline use in Crimson Atlas.

## Findings

### 1. Game-Internal Map Textures
**Status: Possible but unconfirmed for direct map use**

Crimson Desert ships assets in encrypted `.paz` / `.pamt` archives. Multiple community tools can extract these:

- **CDMW-Full** (Ratty123) — Windows portable workbench. Can browse, extract, and rebuild DDS textures from game archives. Read coverage for texture formats is ~80%. Write coverage ~16.7%.
  - Repo: https://github.com/Ratty123/crimson-desert-mod-workbench
  - License: Not explicitly stated; modding tooling with explicit patch/restore flows.
  - Note: Archive browsing/extraction is read-only and does not silently rewrite game archives.

- **pycrimson** (LukeFZ) — Python CLI/library for interacting with game and save files. Implements proper key derivation for `.paz` asset decryption and save-file decryption.
  - Repo: https://github.com/LukeFZ/pycrimson
  - License: Not explicitly stated; credit requested if reused.

- **CrimsonDesertTools** (MrIkso) — Python toolset for unpack/repack of `.paz` archives.
  - Repo: https://github.com/MrIkso/CrimsonDesertTools
  - License: MIT

- **Greymane** (echo000) — WIP asset extractor. Licensed under GPL v3. Explicitly states extracted assets are property of their respective owners.
  - Repo: https://github.com/echo000/Greymane

**Assessment**: Game files likely contain world-map textures or renderable terrain data, but:
- No confirmed single "world map" image suitable for direct tiling has been publicly documented.
- Extracted DDS textures would need to be assembled/stitched into a map projection.
- Extraction requires the user's own legally obtained game files.
- Redistribution of extracted game assets is NOT permitted by these tools' terms.

### 2. Official Pearl Abyss Resources
**Status: No suitable public map artwork found**

Pearl Abyss does not appear to release standalone world-map artwork under an open license. Their official map in-game is rendered from game assets and is not available as a redistributable image.

### 3. Community Redistributable Assets
**Status: None confirmed**

No community project was found that provides a redistributable, license-cleared full-world raster or tile set for Crimson Desert. Community tools focus on extraction/inspection, not redistribution.

### 4. MapGenie / Greymane Codex Structure (Technical Research Only)
**Status: Technical reference only — do NOT copy or embed**

- **MapGenie** (`mapgenie.io/crimson-desert`) provides an interactive iframe-embeddable map with layers for Strongholds, Abyss Cressets, etc. It uses an embed API (`?embed=light`). This is a third-party service and must not be embedded or depended on by Crimson Atlas.

- **Greymane Codex** is referenced in community discussions but no public redistributable tile set was found.

- **Technical structure observed**:
  - Interactive maps of this type typically use one of:
    - A single large raster with coordinate transform
    - XYZ tile pyramid
    - Multiple region/image layers
  - Without access to their tile server or API, exact structure cannot be confirmed.
  - CD Companion (leandrodiogenes) uses an affine transform to calibrate game XYZ to MapGenie lng/lat, suggesting MapGenie uses a projected coordinate system rather than raw game units.

### 5. CD Companion Approach
**Status: Reference only**

The existing `cd-companion` project (leandrodiogenes) embeds MapGenie in a PyQt5 WebEngineView and injects JavaScript to place a marker. This approach:
- Depends on MapGenie's web service
- Uses an iframe/WebView (explicitly forbidden for Crimson Atlas)
- Has default calibrations for Pywel and Abyss realms

Crimson Atlas must not replicate this architecture.

## Conclusion

**No legally redistributable base map image or tile set was found.**

Available paths forward:

### Path A: User-self-extracted game assets (Preferred)
1. User extracts map textures from their own `CrimsonDesert.exe` installation using a tool like CDMW-Full or pycrimson.
2. Crimson Atlas provides tooling to:
   - Inspect extracted assets
   - Identify candidate map textures
   - Convert DDS → PNG/WebP
   - Generate tile pyramids
   - Calibrate game coordinates to image coordinates
3. Assets remain on the user's machine only; nothing is bundled or redistributed.

**Blockers**: The exact archive path and texture name for the world map texture in the game files is not yet documented. This requires either:
- Community reverse-engineering to identify the correct `.paz` path and texture name
- Or manual inspection by a user with extraction tools

### Path B: Procedural / community-contributed calibration over debug grid
Continue with the current debug grid until a base map becomes available. Calibration points collected by users could eventually be shared as coordinate transforms without sharing the underlying map image.

### Path C: Wait for a community asset release
Monitor community projects for a redistributable map asset release. Do not hold development hostage to this — the tile/calibration architecture should be built now so any future map source can be plugged in.

## Recommendation

Proceed with **Path A tooling + Path B fallback**:
1. Build the tile/calibration architecture now (Phase 4).
2. Create `tools/inspect_game_assets.py` to list/extract candidate textures from the user's game install.
3. Keep the debug grid as fallback when no calibrated map is available.
4. Document the manual extraction workflow so technically inclined users can supply their own map texture.

## Terms Summary

| Source | Format | Redistributable? | usable in Crimson Atlas? |
|---|---|---|---|
| Game .paz archives (user's own copy) | DDS textures | NO | YES — local-only, user-extracted |
| CDMW-Full / pycrimson | Extraction tooling | Tool-dependent | YES — as tooling |
| MapGenie iframe/API | Web tiles + JS | NO | NO — forbidden |
| Greymane Codex | Unknown | NO | NO — not confirmed |
| Community tile sets | Unknown | Unknown | NO — not confirmed |

## PAMT Format Findings

### Exact PAMT Flags Bug Fixed

The correct PAMT flags byte format is:
- **Low nibble** = compression (0=NONE, 1=PARTIAL, 2=LZ4, 3=ZLIB, 4=QUICKLZ)
- **High nibble** = crypto (0=NONE, 1=ICE, 2=AES, 3=CHACHA20)

Community tools like crimson-desert-unpacker incorrectly use `(flags >> 16) & 0x0F` instead of the correct single-byte format.

### pycrimson PackMeta Usage

```python
from pycrimson._files._pamt import PackMeta
from pycrimson._crypto import chacha20_decrypt_pack_entry
import lz4.block
import struct

pamt_path = Path(r"G:\Steam\steamapps\common\Crimson Desert\0012\0.pamt")
with open(pamt_path, "rb") as f:
    expected_crc = struct.unpack("<I", f.read(4))[0]

pamt = PackMeta.from_file(pamt_path, expected_crc)
# For each file:
raw = chacha20_decrypt_pack_entry(encrypted_data, pamt.encrypt_data, "path/in/pamt/file.ext")
decompressed = lz4.block.decompress(raw, uncompressed_size=file.uncompressed_size)
```

### Encryption Patterns in Group 0012

| Category | Count | Compression | Crypto |
|---|---|---|---|
| Uncompressed, unencrypted | 20329 | NONE | NONE |
| LZ4 + CHACHA20 | 334 | LZ4 | CHACHA20 |
| NONE + CHACHA20 | 275 | NONE | CHACHA20 |
| LZ4 + NONE | 34 | LZ4 | NONE |

Key findings:
- `navigatortexture.css` is **LZ4+CHACHA20 encrypted** (flags=0x32)
- **All text files** in `ui/xml/` are **CHACHA20 encrypted**
- Worldmap hex tiles are **uncompressed, unencrypted, PARTIAL** (flags=0x00, is_partial=True)

### Key Map Directories Found in Group 0012

| Directory | File Count | Description |
|---|---|---|
| `ui/texture/image/worldmap/` | 1794 | Abyss hex tiles at 32768x32768 |
| `ui/texture/image/worldmapimage/` | 19 | World map images |
| `ui/texture/image/worldmapfog/` | 8 | Fog overlays |
| `ui/texture/image/worldmapregiontitle/` | 234 | Region title images |
| `ui/texture/image/playguideimage/` | 261 | Minimap and advice images |
| `ui/texture/image/commonimage/` | 97 | Common images including backgrounds |
| `ui/xml/navigator/` | 3 | Navigator text files |

### Top Map Texture Candidates

| Path | chunk_id | Offset | Comp Size | Uncomp Size | Flags | Rank | Reason |
|---|---|---|---|---|---|---|---|
| `ui/texture/image/worldmap/cd_worldmap_abyss_hex_sdf_32768x32768_0_0.dds` | 4 | 0x23fbbab0 | 121328 | 349653 | 0x00 | 95 | worldmap hex tile, 32768x32768, numbered sequence |
| `ui/texture/image/worldmap/cd_worldmap_abyss_hex_sdf_32768x32768_0_1.dds` | 4 | 0x23fd94a0 | 128390 | 349653 | 0x00 | 95 | worldmap hex tile, 32768x32768, numbered sequence |
| `ui/texture/image/commonimage/cd_image_abyss_worldmap_bg_hex_00.dds` | 3 | 0x2173c270 | 5243 | 262272 | 0x00 | 90 | worldmap background |
| `ui/texture/image/commonimage/cd_image_worldmap_crime_fog_00.dds` | 3 | 0x21974010 | 135160 | 262272 | 0x00 | 90 | Pywel world map fog |
| `ui/texture/image/worldmapfog/bitmap_region.dds` | 4 | 0x2da8d580 | 507415 | 11184938 | 0x00 | 85 | fog overlay |
| `ui/texture/image/worldmapfog/v_bitmap_region.dds` | 5 | 0x26886170 | 369334 | 44739370 | 0x00 | 85 | fog overlay |
| `ui/texture/image/worldmapregiontitle/cd_worldmap_image_crimsondesert_crime_sdf_4096x4096.dds` | 4 | 0x2eae6750 | 350154 | 1398229 | 0x00 | 80 | region title image |
| `ui/texture/image/playguideimage/cd_playguideimage_advice_minimap.dds` | 2 | 0x352db150 | 134156 | 262272 | 0x00 | 75 | minimap |
| `ui/texture/image/playguideimage/cd_playguideimage_wanted_minimap_target.dds` | 4 | 0x112ed830 | 376359 | 1048706 | 0x00 | 75 | minimap target |
| `ui/xml/navigator/navigatortexture.css` | 0 | 0x18d65e0 | 5159 | 21361 | 0x32 | 10 | navigator texture references |

## Next Actions
1. Build `tools/inspect_game_assets.py` to enumerate `.paz` archives and list candidate map textures.
2. Build tile generation tooling that accepts a user-supplied source image.
3. Complete calibration system (Phase 4 core).
4. Integrate calibrated map into frontend.
