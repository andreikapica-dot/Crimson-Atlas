"""Match road features between an in-game map screenshot and Atlas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = tuple(int(item) for item in value.split(","))
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be x,y,width,height")
    return parts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game", type=Path)
    parser.add_argument("atlas", type=Path)
    parser.add_argument("--game-crop", type=parse_box, required=True)
    parser.add_argument("--atlas-crop", type=parse_box, required=True)
    parser.add_argument("--game-player", required=True, help="Player center x,y in full game screenshot")
    args = parser.parse_args()

    game_full = cv2.imread(str(args.game), cv2.IMREAD_GRAYSCALE)
    atlas_full = cv2.imread(str(args.atlas), cv2.IMREAD_GRAYSCALE)
    if game_full is None or atlas_full is None:
        raise SystemExit("Could not load screenshots")
    gx, gy, gw, gh = args.game_crop
    ax, ay, aw, ah = args.atlas_crop
    game = game_full[gy:gy + gh, gx:gx + gw]
    atlas = atlas_full[ay:ay + ah, ax:ax + aw]

    detector = cv2.SIFT_create(nfeatures=12000, contrastThreshold=0.01)
    game_keys, game_descriptors = detector.detectAndCompute(game, None)
    atlas_keys, atlas_descriptors = detector.detectAndCompute(atlas, None)
    matches = cv2.BFMatcher().knnMatch(game_descriptors, atlas_descriptors, k=2)
    good = [first for first, second in matches if first.distance < 0.68 * second.distance]
    if len(good) < 8:
        raise SystemExit(f"Only {len(good)} reliable matches")

    game_points = np.float32([game_keys[item.queryIdx].pt for item in good]).reshape(-1, 1, 2)
    atlas_points = np.float32([atlas_keys[item.trainIdx].pt for item in good]).reshape(-1, 1, 2)
    transform, inliers = cv2.estimateAffinePartial2D(game_points, atlas_points, method=cv2.RANSAC, ransacReprojThreshold=4.0)
    if transform is None:
        raise SystemExit("Could not estimate screenshot transform")

    player_x, player_y = (float(item) for item in args.game_player.split(","))
    local_player = np.float32([[[player_x - gx, player_y - gy]]])
    projected = cv2.transform(local_player, transform)[0, 0]
    result = {
        "matches": len(good),
        "inliers": int(inliers.sum()),
        "atlasExpectedPlayer": [float(projected[0] + ax), float(projected[1] + ay)],
        "transform": transform.tolist(),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
