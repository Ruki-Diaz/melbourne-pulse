import { Suspense } from "react";
import { preload } from "react-dom";

import { PlanClient } from "@/components/plan/PlanClient";
import { PlanIntro } from "@/components/plan/PlanIntro";

/**
 * /plan: pick a time to be in the CBD from forecast foot traffic and rain.
 * The page itself is static. It reads its options from the URL and its data
 * from /api/plan in the browser (components/plan/PlanClient.tsx).
 */
export default function PlanPage() {
  // Start the default plan request with the HTML, so it is already under way when the script asks for it.
  preload("/api/plan?sensor=cbd&window=36h", { as: "fetch", crossOrigin: "anonymous" });
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[#05080D]">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
            <PlanIntro />
          </div>
        </main>
      }
    >
      <PlanClient />
    </Suspense>
  );
}
