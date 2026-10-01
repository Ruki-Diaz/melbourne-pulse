import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Plan your CBD visit · Melbourne Pulse",
  description:
    "Forecast foot traffic and the chance of rain, hour by hour, for Melbourne's CBD or any pedestrian sensor. Pick the busiest dry hours, the most foot traffic or the quietest time.",
  openGraph: {
    title: "Plan your CBD visit · Melbourne Pulse",
    description: "Forecast foot traffic and the chance of rain, hour by hour, to pick your time in Melbourne's CBD.",
  },
};

export default function PlanLayout({ children }: { children: React.ReactNode }) {
  return children;
}
