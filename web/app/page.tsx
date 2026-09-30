import { getLatest, type Summary } from "@/lib/db";

// Regenerated at most hourly, and on demand by /api/revalidate after each
// ingest, so visitors almost never wake the database. See README "Free-tier budget".
export const revalidate = 3600;

// Placeholder until Phase 3 builds the map: proves the read-only DB path works.
export default async function Home() {
  const summary = await getLatest<Summary>("summary");

  return (
    <main className="flex flex-1 items-center justify-center bg-zinc-950 p-6 text-zinc-100">
      <div className="max-w-xl space-y-3 text-center">
        <h1 className="text-sm font-semibold tracking-widest text-zinc-400 uppercase">Melbourne Pulse</h1>
        <p className="text-xl leading-relaxed">
          {summary?.payload.text ?? "Waiting for the first data from the hourly pipeline."}
        </p>
        {summary && (
          <p className="text-sm text-zinc-500">Updated {summary.updatedAt.toISOString()}</p>
        )}
      </div>
    </main>
  );
}
