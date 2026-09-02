/** Generate a local MapLibre style for the Crimson Atlas debug grid map.
 *
 * No external tiles. No remote fonts. Works completely offline.
 */

import type { StyleSpecification } from "maplibre-gl";

export interface GridOptions {
  min: number;
  max: number;
  majorStep: number;
  minorStep: number;
}

function buildGridLines(opts: GridOptions) {
  const majorFeatures: any[] = [];
  const minorFeatures: any[] = [];

  for (let i = opts.min; i <= opts.max; i += opts.minorStep) {
    const isMajor = i !== 0 && i % opts.majorStep === 0;
    const features = isMajor ? majorFeatures : minorFeatures;

    features.push({
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: [[i, opts.min], [i, opts.max]] },
    });

    features.push({
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: [[opts.min, i], [opts.max, i]] },
    });
  }

  return { majorFeatures, minorFeatures };
}

export function createDebugGrid(opts: GridOptions) {
  return buildGridLines(opts);
}

export function createDebugMapStyle(grid: ReturnType<typeof createDebugGrid>): StyleSpecification {
  return {
    version: 8,
    name: "Crimson Atlas Debug",
    center: [0, 0],
    zoom: 13,
    sources: {
      "grid-minor": {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: grid.minorFeatures,
        },
      },
      "grid-major": {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: grid.majorFeatures,
        },
      },
      "origin-marker": {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: {},
              geometry: { type: "Point", coordinates: [0, 0] },
            },
          ],
        },
      },
    },
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "#0f0f1a" },
      },
      {
        id: "grid-minor",
        type: "line",
        source: "grid-minor",
        paint: { "line-color": "#1a1a2e", "line-width": 1 },
      },
      {
        id: "grid-major",
        type: "line",
        source: "grid-major",
        paint: { "line-color": "#2d2d44", "line-width": 2 },
      },
      {
        id: "origin-marker",
        type: "circle",
        source: "origin-marker",
        paint: {
          "circle-radius": 8,
          "circle-color": "#ff6060",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      },
    ],
  };
}
