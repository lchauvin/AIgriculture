"use client";

import { useMemo } from "react";
import Map, {
  Layer,
  NavigationControl,
  Source,
} from "react-map-gl/maplibre";
import type { StyleSpecification } from "maplibre-gl";
import type { FeatureCollection } from "geojson";

import type { Bbox, CropSuitabilityGrid } from "@/app/lib/api";

const ESRI_ATTRIBUTION =
  "Tiles &copy; Esri — Esri, i-cubed, USDA, USGS, AEX, GeoEye, " +
  "Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community";

/** Esri World Imagery basemap — the closest open analog to Google Earth's
 * satellite layer. No API key required; free for non-commercial use. */
const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    "esri-world-imagery": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/" +
          "World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution: ESRI_ATTRIBUTION,
      maxzoom: 18,
    },
  },
  layers: [
    {
      id: "esri-world-imagery",
      type: "raster",
      source: "esri-world-imagery",
    },
  ],
};

interface MapViewProps {
  bbox: Bbox;
  /** When set, draw a colored polygon grid overlay (one polygon per cell). */
  gridOverlay?: CropSuitabilityGrid | null;
}

export default function MapView({ bbox, gridOverlay }: MapViewProps) {
  const bboxGeoJSON = useMemo(() => bboxFeatureCollection(bbox), [bbox]);
  const gridGeoJSON = useMemo(
    () => (gridOverlay ? gridFeatureCollection(gridOverlay) : null),
    [gridOverlay],
  );

  // Center on the centroid of the bbox with a reasonable zoom for a
  // 1-2° sub-region.
  const center = useMemo<{ longitude: number; latitude: number; zoom: number }>(
    () => ({
      longitude: (bbox[0] + bbox[2]) / 2,
      latitude: (bbox[1] + bbox[3]) / 2,
      zoom: 7.5,
    }),
    // intentionally not depending on bbox — initial view only; user pans freely after.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  return (
    <Map
      initialViewState={center}
      style={{ width: "100%", height: "100%" }}
      mapStyle={MAP_STYLE}
      attributionControl={true}
    >
      <NavigationControl position="top-left" showCompass={false} />

      {/* The bbox rectangle — always shown. */}
      <Source id="bbox" type="geojson" data={bboxGeoJSON}>
        <Layer
          id="bbox-fill"
          type="fill"
          paint={{ "fill-color": "#facc15", "fill-opacity": 0.08 }}
        />
        <Layer
          id="bbox-outline"
          type="line"
          paint={{ "line-color": "#facc15", "line-width": 2 }}
        />
      </Source>

      {/* Optional per-cell suitability grid. */}
      {gridGeoJSON && (
        <Source id="grid" type="geojson" data={gridGeoJSON}>
          <Layer
            id="grid-fill"
            type="fill"
            paint={{
              "fill-color": [
                "interpolate",
                ["linear"],
                ["get", "score"],
                0,
                "#a50026",
                0.25,
                "#f46d43",
                0.5,
                "#fee08b",
                0.75,
                "#a6d96a",
                1,
                "#1a9850",
              ],
              "fill-opacity": 0.55,
            }}
          />
          <Layer
            id="grid-outline"
            type="line"
            paint={{ "line-color": "#0f172a", "line-width": 0.2 }}
          />
        </Source>
      )}
    </Map>
  );
}

function bboxFeatureCollection(bbox: Bbox): FeatureCollection {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [minLon, minLat],
              [maxLon, minLat],
              [maxLon, maxLat],
              [minLon, maxLat],
              [minLon, minLat],
            ],
          ],
        },
        properties: {},
      },
    ],
  };
}

function gridFeatureCollection(grid: CropSuitabilityGrid): FeatureCollection {
  const [dLat, dLon] = grid.cell_size_deg;
  const features: FeatureCollection["features"] = [];
  for (let i = 0; i < grid.lats.length; i++) {
    for (let j = 0; j < grid.lons.length; j++) {
      const score = grid.score_grid[i]?.[j];
      if (score === null || score === undefined) continue;
      const lat = grid.lats[i];
      const lon = grid.lons[j];
      const minLat = lat - dLat / 2;
      const maxLat = lat + dLat / 2;
      const minLon = lon - dLon / 2;
      const maxLon = lon + dLon / 2;
      features.push({
        type: "Feature",
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [minLon, minLat],
              [maxLon, minLat],
              [maxLon, maxLat],
              [minLon, maxLat],
              [minLon, minLat],
            ],
          ],
        },
        properties: { score, lat, lon },
      });
    }
  }
  return { type: "FeatureCollection", features };
}
