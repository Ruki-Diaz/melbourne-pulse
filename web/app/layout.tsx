import type { Metadata, Viewport } from "next";
import { Space_Grotesk, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-heading",
  subsets: ["latin"],
  display: "swap",
});

const dmSans = DM_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

export const viewport: Viewport = {
  themeColor: "#05080D",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "https://melbourne-pulse.vercel.app"
  ),
  title: "Melbourne Pulse · Live Pedestrian Counts & Parking Telemetry",
  description:
    "Live pedestrian activity, free on-street parking bays, and 24-hour LightGBM machine learning forecasts across Melbourne CBD. Runs on $0.",
  keywords: [
    "Melbourne",
    "CBD",
    "live pedestrian counts",
    "parking bays",
    "machine learning forecast",
    "civic telemetry",
    "City of Melbourne open data",
  ],
  authors: [{ name: "Rukshan Dias", url: "https://github.com/Ruki-Diaz" }],
  openGraph: {
    title: "Melbourne Pulse · Live Pedestrian Counts & Parking Telemetry",
    description:
      "See how busy the Melbourne CBD is right now, and what the next 24 hours look like. Zero-cost civic analytics.",
    siteName: "Melbourne Pulse",
    type: "website",
    locale: "en_AU",
  },
  twitter: {
    card: "summary_large_image",
    title: "Melbourne Pulse · Live Pedestrian Counts & Parking Telemetry",
    description:
      "See how busy the Melbourne CBD is right now, and what the next 24 hours look like. Zero-cost civic analytics.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${dmSans.variable} ${jetbrainsMono.variable} dark bg-[#05080D]`}
    >
      <body className="min-h-screen flex flex-col bg-[#05080D] text-slate-100 font-['DM_Sans',sans-serif] antialiased">
        <Navbar />
        <div className="flex-1">{children}</div>
        <Footer />
      </body>
    </html>
  );
}
