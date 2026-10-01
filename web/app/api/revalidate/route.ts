import { createHash, timingSafeEqual } from "node:crypto";

import { revalidatePath, revalidateTag } from "next/cache";

import { PLAN_CACHE_TAG } from "@/lib/plan";

/**
 * Called by the hourly GitHub Action right after new data lands:
 *   curl -X POST "$SITE_URL/api/revalidate" -H "Authorization: Bearer $REVALIDATE_SECRET"
 * Marks every page stale so the next request re-reads the database. The
 * Action then requests "/" once, so that happens while Neon is still awake.
 */
export async function POST(request: Request) {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret) {
    return Response.json({ ok: false, error: "REVALIDATE_SECRET not configured" }, { status: 500 });
  }
  if (!matches(request.headers.get("authorization") ?? "", `Bearer ${secret}`)) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  revalidatePath("/", "layout");
  // The Plan API's cached database snapshot. { expire: 0 }: the next request
  // (the Action's own warm-up call) re-reads the database instead of getting old data.
  revalidateTag(PLAN_CACHE_TAG, { expire: 0 });
  return Response.json({ ok: true, revalidatedAt: new Date().toISOString() });
}

/** Constant-time comparison (hashing first makes the lengths equal). */
function matches(given: string, expected: string) {
  const digest = (value: string) => createHash("sha256").update(value).digest();
  return timingSafeEqual(digest(given), digest(expected));
}
