"""Estimate an Abyss texture-to-screenshot transform for calibration evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("screenshot", type=Path)
    parser.add_argument("--player-screen", required=True, help="Player marker center as x,y")
    args = parser.parse_args()

    source = cv2.imread(str(args.source), cv2.IMREAD_UNCHANGED)
    screenshot = cv2.imread(str(args.screenshot), cv2.IMREAD_COLOR)
    if source is None or screenshot is None or source.shape[2] != 4:
        raise SystemExit("Could not load source RGBA image or screenshot")

    alpha_points = cv2.findNonZero((source[:, :, 3] > 16).astype(np.uint8))
    x, y, width, height = cv2.boundingRect(alpha_points)
    crop = source[y:y + height, x:x + width, :3]
    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    screen_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

    detector = cv2.SIFT_create(nfeatures=8000, contrastThreshold=0.015)
    source_keys, source_descriptors = detector.detectAndCompute(crop_gray, None)
    screen_keys, screen_descriptors = detector.detectAndCompute(screen_gray, None)
    matches = cv2.BFMatcher().knnMatch(source_descriptors, screen_descriptors, k=2)
    good = [first for first, second in matches if first.distance < 0.72 * second.distance]
    if len(good) < 8:
        raise SystemExit(f"Only {len(good)} reliable feature matches")

    source_points = np.float32([source_keys[item.queryIdx].pt for item in good]).reshape(-1, 1, 2)
    screen_points = np.float32([screen_keys[item.trainIdx].pt for item in good]).reshape(-1, 1, 2)
    homography, inliers = cv2.findHomography(source_points, screen_points, cv2.RANSAC, 4.0)
    if homography is None:
        raise SystemExit("Could not estimate homography")

    player_x, player_y = (float(part) for part in args.player_screen.split(","))
    inverse = np.linalg.inv(homography)
    player_crop = cv2.perspectiveTransform(
        np.float32([[[player_x, player_y]]]), inverse,
    )[0, 0]
    result = {
        "sourceAlphaBounds": [x, y, width, height],
        "matches": len(good),
        "inliers": int(inliers.sum()),
        "playerSourcePixel": [float(player_crop[0] + x), float(player_crop[1] + y)],
        "homography": homography.tolist(),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
