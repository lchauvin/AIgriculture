"use client";

import { useCallback, useMemo, useRef } from "react";
import Map, {
  Layer,
  NavigationControl,
  Source,
  type MapRef,
  type MapLayerMouseEvent,
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

// Pixel tolerance for considering the cursor to be "on" a bbox edge.
const EDGE_TOLERANCE_PX = 8;
// Minimum bbox side, in degrees — prevents the user from dragging the
// W edge past the E edge (or analogously for N/S) and creating an
// inverted rectangle the backend would reject anyway.
const MIN_SIDE_DEG = 0.1;

interface MapViewProps {
  bbox: Bbox;
  /** When set, draw a colored polygon grid overlay (one polygon per cell). */
  gridOverlay?: CropSuitabilityGrid | null;
  /** When set, the bbox rectangle becomes interactive — hover the edges
   * to resize, hover inside to translate. The callback fires on each
   * mousemove during a drag, so the parent can keep the sidebar inputs
   * in sync live. */
  onBboxChange?: (bbox: Bbox) => void;
}

type EdgeFlags = {
  n: boolean;
  s: boolean;
  e: boolean;
  w: boolean;
  interior: boolean;
};

const NO_EDGES: EdgeFlags = {
  n: false,
  s: false,
  e: false,
  w: false,
  interior: false,
};

interface DragState {
  startBbox: Bbox;
  startLngLat: { lng: number; lat: number };
  edges: EdgeFlags;
}

export default function MapView({ bbox, gridOverlay, onBboxChange }: MapViewProps) {
  const bboxGeoJSON = useMemo(() => bboxFeatureCollection(bbox), [bbox]);
  const gridGeoJSON = useMemo(
    () => (gridOverlay ? gridFeatureCollection(gridOverlay) : null),
    [gridOverlay],
  );

  const mapRef = useRef<MapRef | null>(null);
  const dragRef = useRef<DragState | null>(null);

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

  const handleMouseMove = useCallback(
    (e: MapLayerMouseEvent) => {
      if (!onBboxChange) return;
      const map = mapRef.current?.getMap();
      if (!map) return;
      const canvas = map.getCanvas();

      if (dragRef.current) {
        // Active drag — compute new bbox from delta in lng/lat space.
        const drag = dragRef.current;
        const dLng = e.lngLat.lng - drag.startLngLat.lng;
        const dLat = e.lngLat.lat - drag.startLngLat.lat;
        const newBbox = applyDrag(drag.startBbox, drag.edges, dLng, dLat);
        onBboxChange(newBbox);
      } else {
        // Hover — update the cursor based on proximity to bbox edges.
        const edges = detectEdges(map, e.point, bbox);
        canvas.style.cursor = cursorFor(edges);
      }
    },
    [bbox, onBboxChange],
  );

  const handleMouseDown = useCallback(
    (e: MapLayerMouseEvent) => {
      if (!onBboxChange) return;
      const map = mapRef.current?.getMap();
      if (!map) return;
      const edges = detectEdges(map, e.point, bbox);
      if (!edges.interior && !edges.n && !edges.s && !edges.e && !edges.w) {
        return; // not on the bbox → let the map handle normal panning
      }
      e.preventDefault(); // suppress map pan while we drag the bbox
      dragRef.current = {
        startBbox: [...bbox] as Bbox,
        startLngLat: { lng: e.lngLat.lng, lat: e.lngLat.lat },
        edges,
      };
      map.getCanvas().style.cursor = cursorFor(edges);
    },
    [bbox, onBboxChange],
  );

  const handleMouseUp = useCallback(() => {
    if (!dragRef.current) return;
    dragRef.current = null;
    const canvas = mapRef.current?.getMap().getCanvas();
    if (canvas) canvas.style.cursor = "";
  }, []);

  const handleMouseLeave = useCallback(() => {
    handleMouseUp();
  }, [handleMouseUp]);

  return (
    <Map
      ref={mapRef}
      initialViewState={center}
      style={{ width: "100%", height: "100%" }}
      mapStyle={MAP_STYLE}
      attributionControl={true}
      onMouseMove={handleMouseMove}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    >
      <NavigationControl position="top-left" showCompass={false} />

      {/* The bbox rectangle — always shown; interactive when onBboxChange is set. */}
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

// ---- bbox geometry helpers --------------------------------------------------

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

// ---- bbox drag logic --------------------------------------------------------

/** Classify the pointer's relationship to a bbox in pixel space. */
function detectEdges(
  map: maplibregl.Map,
  pointPx: { x: number; y: number },
  bbox: Bbox,
): EdgeFlags {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  // Screen-y increases downward; lat increases upward.
  // So maxLat → smaller y (top), minLat → larger y (bottom).
  const sw = map.project([minLon, minLat]);
  const ne = map.project([maxLon, maxLat]);
  const left = sw.x;
  const right = ne.x;
  const top = ne.y;
  const bottom = sw.y;

  const insideX = pointPx.x >= left - EDGE_TOLERANCE_PX && pointPx.x <= right + EDGE_TOLERANCE_PX;
  const insideY = pointPx.y >= top - EDGE_TOLERANCE_PX && pointPx.y <= bottom + EDGE_TOLERANCE_PX;
  if (!insideX || !insideY) return NO_EDGES;

  const nearW = Math.abs(pointPx.x - left) <= EDGE_TOLERANCE_PX;
  const nearE = Math.abs(pointPx.x - right) <= EDGE_TOLERANCE_PX;
  const nearN = Math.abs(pointPx.y - top) <= EDGE_TOLERANCE_PX;
  const nearS = Math.abs(pointPx.y - bottom) <= EDGE_TOLERANCE_PX;

  if (nearN || nearS || nearE || nearW) {
    return { n: nearN, s: nearS, e: nearE, w: nearW, interior: false };
  }
  // Inside the rectangle and not near any edge → translate.
  return { n: false, s: false, e: false, w: false, interior: true };
}

function cursorFor(edges: EdgeFlags): string {
  if (!edges.interior && !edges.n && !edges.s && !edges.e && !edges.w) return "";
  if ((edges.n && edges.w) || (edges.s && edges.e)) return "nwse-resize";
  if ((edges.n && edges.e) || (edges.s && edges.w)) return "nesw-resize";
  if (edges.n || edges.s) return "ns-resize";
  if (edges.e || edges.w) return "ew-resize";
  return "move";
}

/** Apply a (lng, lat) delta to the start bbox, given which edges are
 * grabbed. Enforces a minimum side length so the rectangle can't be
 * inverted past its opposite edge. */
function applyDrag(
  startBbox: Bbox,
  edges: EdgeFlags,
  dLng: number,
  dLat: number,
): Bbox {
  let [minLon, minLat, maxLon, maxLat] = startBbox;

  if (edges.interior) {
    // Translate the whole rectangle.
    minLon += dLng;
    maxLon += dLng;
    minLat += dLat;
    maxLat += dLat;
    return [minLon, minLat, maxLon, maxLat];
  }

  if (edges.w) {
    // Don't let W cross E (with a small minimum side).
    minLon = Math.min(minLon + dLng, maxLon - MIN_SIDE_DEG);
  }
  if (edges.e) {
    maxLon = Math.max(maxLon + dLng, minLon + MIN_SIDE_DEG);
  }
  if (edges.s) {
    minLat = Math.min(minLat + dLat, maxLat - MIN_SIDE_DEG);
  }
  if (edges.n) {
    maxLat = Math.max(maxLat + dLat, minLat + MIN_SIDE_DEG);
  }
  return [minLon, minLat, maxLon, maxLat];
}
