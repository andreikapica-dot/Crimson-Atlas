"""Build an improved local Pywel tile pyramid from the public MapGenie layer.

The source is registered against the existing TH.GL-derived map and composited
over it, so game coordinates, markers, and teleport calibration do not change.
Game files are never read or modified by this utility.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import functools
import math
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


SOURCE_ZOOM = 15
SOURCE_TILE_SIZE = 256
TARGET_ZOOM = 6
TARGET_TILE_SIZE = 512
SOURCE_MOSAIC_ORIGIN_Z11 = np.array([260096.0, 260096.0])

# Robust affine registration from the MapGenie z11 research mosaic to the
# existing local z3 pyramid. Median inlier error: 0.70 px at local zoom 3.
REGISTERED_AFFINE = np.array(
    [
        [3.48596636, -0.00162018933, -1644.49693],
        [0.000232261333, 3.48812656, -1464.31250],
    ],
    dtype=np.float64,
)

# Non-black bounds of the Pywel sheet in the z11 research mosaic.
PYWEL_SOURCE_BOUNDS_Z11 = (624, 619, 1419, 1406)
SOURCE_URL = (
    "https://tiles.mapgenie.io/games/crimson-desert/pywel/"
    "default-v3/{z}/{y}/{x}.jpg"
)


def source_to_target_affine() -> np.ndarray:
    """Return an affine mapping from global source-z15 to target-z6 pixels."""

    linear = REGISTERED_AFFINE[:, :2]
    translation = REGISTERED_AFFINE[:, 2]
    source_zoom_factor = 2 ** (SOURCE_ZOOM - 11)
    target_zoom_factor = 2 ** (TARGET_ZOOM - 3)
    result = np.empty((2, 3), dtype=np.float64)
    result[:, :2] = target_zoom_factor * linear / source_zoom_factor
    result[:, 2] = target_zoom_factor * (
        translation - linear @ SOURCE_MOSAIC_ORIGIN_Z11
    )
    return result


def download_tile(cache_root: Path, x: int, y: int) -> Path:
    path = cache_root / str(SOURCE_ZOOM) / str(y) / f"{x}.jpg"
    if path.exists() and path.stat().st_size > 100:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        SOURCE_URL.format(z=SOURCE_ZOOM, y=y, x=x),
        headers={"User-Agent": "Crimson Atlas personal offline map builder"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        path.write_bytes(response.read())
    return path


def build_max_zoom(
    base_root: Path,
    output_root: Path,
    cache_root: Path,
) -> None:
    transform = source_to_target_affine()
    inverse_linear = np.linalg.inv(transform[:, :2])

    source_scale = 2 ** (SOURCE_ZOOM - 11)
    sx0, sy0, sx1, sy1 = PYWEL_SOURCE_BOUNDS_Z11
    source_corners = np.array(
        [
            [(SOURCE_MOSAIC_ORIGIN_Z11[0] + sx0) * source_scale,
             (SOURCE_MOSAIC_ORIGIN_Z11[1] + sy0) * source_scale],
            [(SOURCE_MOSAIC_ORIGIN_Z11[0] + sx1) * source_scale,
             (SOURCE_MOSAIC_ORIGIN_Z11[1] + sy1) * source_scale],
        ]
    )
    target_corners = source_corners @ transform[:, :2].T + transform[:, 2]
    min_tile = np.floor(target_corners.min(axis=0) / TARGET_TILE_SIZE).astype(int) - 1
    max_tile = np.ceil(target_corners.max(axis=0) / TARGET_TILE_SIZE).astype(int) + 1
    min_tile = np.maximum(min_tile, 0)
    max_tile = np.minimum(max_tile, 2**TARGET_ZOOM - 1)

    source_tile_min = np.floor(source_corners.min(axis=0) / SOURCE_TILE_SIZE).astype(int) - 2
    source_tile_max = np.ceil(source_corners.max(axis=0) / SOURCE_TILE_SIZE).astype(int) + 2
    source_jobs = [
        (x, y)
        for y in range(int(source_tile_min[1]), int(source_tile_max[1]) + 1)
        for x in range(int(source_tile_min[0]), int(source_tile_max[0]) + 1)
    ]

    def prefetch(job: tuple[int, int]) -> None:
        download_tile(cache_root, job[0], job[1])

    print(f"source cache: {len(source_jobs)} tiles", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        for index, _ in enumerate(pool.map(prefetch, source_jobs), start=1):
            if index % 250 == 0 or index == len(source_jobs):
                print(f"source cache: {index}/{len(source_jobs)}", flush=True)

    @functools.lru_cache(maxsize=192)
    def load_source_tile(x: int, y: int) -> np.ndarray:
        path = download_tile(cache_root, x, y)
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Cannot decode source tile: {path}")
        return image

    total = int((max_tile[0] - min_tile[0] + 1) * (max_tile[1] - min_tile[1] + 1))
    done = 0
    for target_y in range(int(min_tile[1]), int(max_tile[1]) + 1):
        for target_x in range(int(min_tile[0]), int(max_tile[0]) + 1):
            target_origin = np.array(
                [target_x * TARGET_TILE_SIZE, target_y * TARGET_TILE_SIZE],
                dtype=np.float64,
            )
            target_box = np.array(
                [
                    target_origin + [-3, -3],
                    target_origin + [TARGET_TILE_SIZE + 3, -3],
                    target_origin + [-3, TARGET_TILE_SIZE + 3],
                    target_origin + [TARGET_TILE_SIZE + 3, TARGET_TILE_SIZE + 3],
                ]
            )
            source_box = (target_box - transform[:, 2]) @ inverse_linear.T
            source_min = np.floor(source_box.min(axis=0)).astype(int) - 3
            source_max = np.ceil(source_box.max(axis=0)).astype(int) + 3
            tile_min = np.floor(source_min / SOURCE_TILE_SIZE).astype(int)
            tile_max = np.floor(source_max / SOURCE_TILE_SIZE).astype(int)
            patch_origin = tile_min * SOURCE_TILE_SIZE
            patch_size = (tile_max - tile_min + 1) * SOURCE_TILE_SIZE
            patch = np.zeros((int(patch_size[1]), int(patch_size[0]), 3), dtype=np.uint8)
            for source_y in range(int(tile_min[1]), int(tile_max[1]) + 1):
                for source_x in range(int(tile_min[0]), int(tile_max[0]) + 1):
                    image = load_source_tile(source_x, source_y)
                    px = (source_x - tile_min[0]) * SOURCE_TILE_SIZE
                    py = (source_y - tile_min[1]) * SOURCE_TILE_SIZE
                    patch[py : py + SOURCE_TILE_SIZE, px : px + SOURCE_TILE_SIZE] = image

            local_transform = transform.copy()
            local_transform[:, 2] = (
                transform[:, :2] @ patch_origin + transform[:, 2] - target_origin
            )
            inset = 8 * source_scale
            feather = 20 * source_scale
            left = (SOURCE_MOSAIC_ORIGIN_Z11[0] + sx0) * source_scale + inset
            top = (SOURCE_MOSAIC_ORIGIN_Z11[1] + sy0) * source_scale + inset
            right = (SOURCE_MOSAIC_ORIGIN_Z11[0] + sx1) * source_scale - inset
            bottom = (SOURCE_MOSAIC_ORIGIN_Z11[1] + sy1) * source_scale - inset
            global_x = patch_origin[0] + np.arange(patch.shape[1], dtype=np.float32)
            global_y = patch_origin[1] + np.arange(patch.shape[0], dtype=np.float32)
            horizontal = np.minimum(global_x - left, right - global_x)[None, :]
            vertical = np.minimum(global_y - top, bottom - global_y)[:, None]
            source_alpha = np.clip(np.minimum(horizontal, vertical) / feather, 0.0, 1.0)
            source_alpha = source_alpha * source_alpha * (3.0 - 2.0 * source_alpha)
            premultiplied = patch.astype(np.float32) * source_alpha[:, :, None]

            warped_premultiplied = cv2.warpAffine(
                premultiplied,
                local_transform,
                (TARGET_TILE_SIZE, TARGET_TILE_SIZE),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
            )
            alpha = cv2.warpAffine(
                source_alpha,
                local_transform,
                (TARGET_TILE_SIZE, TARGET_TILE_SIZE),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
            )
            warped = warped_premultiplied / np.maximum(alpha[:, :, None], 1e-5)

            base_path = base_root / str(TARGET_ZOOM) / str(target_y) / f"{target_x}.webp"
            if not base_path.exists():
                raise FileNotFoundError(base_path)
            base = cv2.imread(str(base_path), cv2.IMREAD_COLOR)
            # Retain the clean palette of the old map while importing the
            # source's roads, labels, settlement shapes, and terrain detail.
            # Low-frequency colour correction removes the rectangular paper
            # sheet without erasing its useful line work.
            difference = base.astype(np.float32) - warped
            small_difference = cv2.resize(difference, (64, 64), interpolation=cv2.INTER_AREA)
            small_delta = cv2.GaussianBlur(
                small_difference,
                (0, 0),
                4.0,
                borderType=cv2.BORDER_REFLECT,
            )
            colour_delta = cv2.resize(
                small_delta,
                (TARGET_TILE_SIZE, TARGET_TILE_SIZE),
                interpolation=cv2.INTER_CUBIC,
            )
            warped = np.clip(warped + colour_delta, 0, 255)
            alpha = alpha[:, :, None]
            composite = np.clip(warped * alpha + base * (1.0 - alpha), 0, 255).astype(np.uint8)
            output_path = output_root / str(TARGET_ZOOM) / str(target_y) / f"{target_x}.webp"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(cv2.cvtColor(composite, cv2.COLOR_BGR2RGB)).save(
                output_path,
                "WEBP",
                quality=92,
                method=5,
            )
            done += 1
            if done % 100 == 0 or done == total:
                print(f"max zoom: {done}/{total}", flush=True)

    # Copy untouched max-zoom tiles so the staging tree is complete.
    for y in range(2**TARGET_ZOOM):
        for x in range(2**TARGET_ZOOM):
            destination = output_root / str(TARGET_ZOOM) / str(y) / f"{x}.webp"
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(base_root / str(TARGET_ZOOM) / str(y) / f"{x}.webp") as image:
                image.save(destination, "WEBP", quality=92, method=5)


def build_lower_zooms(output_root: Path) -> None:
    for zoom in range(TARGET_ZOOM - 1, -1, -1):
        child_zoom = zoom + 1
        count = 2**zoom
        for y in range(count):
            for x in range(count):
                canvas = Image.new("RGB", (TARGET_TILE_SIZE * 2, TARGET_TILE_SIZE * 2))
                for dy in range(2):
                    for dx in range(2):
                        child = output_root / str(child_zoom) / str(y * 2 + dy) / f"{x * 2 + dx}.webp"
                        with Image.open(child) as image:
                            canvas.paste(image.convert("RGB"), (dx * TARGET_TILE_SIZE, dy * TARGET_TILE_SIZE))
                tile = canvas.resize((TARGET_TILE_SIZE, TARGET_TILE_SIZE), Image.Resampling.LANCZOS)
                destination = output_root / str(zoom) / str(y) / f"{x}.webp"
                destination.parent.mkdir(parents=True, exist_ok=True)
                tile.save(destination, "WEBP", quality=92, method=5)
        print(f"zoom {zoom}: {count * count} tiles", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("frontend/public/maps/pywel"))
    parser.add_argument("--output", type=Path, default=Path("work/mapgenie_pywel_tiles"))
    parser.add_argument("--cache", type=Path, default=Path("work/mapgenie_source_tiles"))
    args = parser.parse_args()
    build_max_zoom(args.base, args.output, args.cache)
    build_lower_zooms(args.output)


if __name__ == "__main__":
    main()
