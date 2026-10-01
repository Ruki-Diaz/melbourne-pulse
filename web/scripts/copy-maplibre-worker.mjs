// MapLibre GL 6 loads its web worker from a file next to its own module.
// Next bundles and renames that module, so the worker would 404. Copy the
// worker (and the shared chunk it imports) into public/ under the installed
// version, and LiveLeafletMap points MapLibre at it with setWorkerUrl().
import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = join(root, "node_modules", "maplibre-gl");
const { version } = JSON.parse(readFileSync(join(pkg, "package.json"), "utf8"));
const out = join(root, "public", "maplibre", version);

mkdirSync(out, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(pkg, "dist", file), join(out, file));
}
console.log(`maplibre worker ${version} -> public/maplibre/${version}/`);
