import "server-only";

import { neon } from "@neondatabase/serverless";

/**
 * Read-only Neon connection over HTTP, for server components only.
 * `server-only` makes the build fail if this is ever imported into client code,
 * so DATABASE_URL_READONLY can't leak to the browser.
 */
function sql() {
  const url = process.env.DATABASE_URL_READONLY;
  return url ? neon(url, { readOnly: true }) : null;
}

export type Latest<T> = { updatedAt: Date; payload: T };

export type Summary = {
  text: string;
  source: "gemini" | "template";
  hour: string | null;
};

/** One `latest` row, or null if the database isn't configured or has no row yet. */
export async function getLatest<T>(source: "parking" | "pedestrian" | "sensors" | "summary") {
  const query = sql();
  if (!query) return null;
  const rows = await query`select updated_at, payload from latest where source = ${source}`;
  const row = rows[0];
  return row ? ({ updatedAt: new Date(row.updated_at), payload: row.payload as T } satisfies Latest<T>) : null;
}
