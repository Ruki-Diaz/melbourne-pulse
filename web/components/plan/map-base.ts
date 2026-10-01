import L from "leaflet";
import { getVersion, setWorkerUrl } from "maplibre-gl";
import { maplibreGL } from "@maplibre/maplibre-gl-leaflet";

/**
 * The same dark basemap as /map (OpenFreeMap, free, no key), for the two small
 * maps on the Plan page. The attribution bar stays on: the basemap's licence
 * requires it.
 */
export function createCbdMap(container: HTMLElement): L.Map {
  // MapLibre's worker is served from public/ (scripts/copy-maplibre-worker.mjs).
  setWorkerUrl(`/maplibre/${getVersion()}/maplibre-gl-worker.mjs`);

  const map = L.map(container, {
    center: [-37.8136, 144.9631],
    zoom: 14,
    minZoom: 12,
    maxZoom: 18,
    zoomControl: true,
    scrollWheelZoom: false, // the page scrolls past the map; zoom with the buttons or a pinch
  });
  map.attributionControl.setPrefix(false);
  maplibreGL({
    style: "https://tiles.openfreemap.org/styles/dark",
    attributionControl: {
      customAttribution:
        '<a href="https://openfreemap.org" target="_blank" rel="noreferrer">OpenFreeMap</a> ' +
        '<a href="https://www.openmaptiles.org/" target="_blank" rel="noreferrer">&copy; OpenMapTiles</a> ' +
        'Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> · ' +
        "City of Melbourne Open Data",
    },
  }).addTo(map);
  return map;
}
