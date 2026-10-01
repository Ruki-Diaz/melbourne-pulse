import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://melbourne-pulse-au.vercel.app";

/** /sitemap.xml: the four public pages. The live pages change every hour. */
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${SITE}/`, changeFrequency: "hourly", priority: 1 },
    { url: `${SITE}/map`, changeFrequency: "hourly", priority: 0.8 },
    { url: `${SITE}/plan`, changeFrequency: "hourly", priority: 0.8 },
    { url: `${SITE}/about`, changeFrequency: "monthly", priority: 0.5 },
  ];
}
