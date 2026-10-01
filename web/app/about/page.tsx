import React from "react";
import Image from "next/image";
import {
  Brain,
  Cpu,
  DollarSign,
  Layers,
  AlertCircle,
} from "lucide-react";

export const revalidate = 3600;

export const metadata = {
  title: "About & Architecture · Melbourne Pulse",
  description: "Architecture, machine learning forecast evaluation, free-tier budget, and open civic data provenance.",
};

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-[#05080D] text-slate-200 py-16 px-4 sm:px-6">
      <div className="max-w-4xl mx-auto space-y-16">
        {/* Header */}
        <div>
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-teal-950/60 border border-teal-500/30 text-teal-300 text-xs font-mono mb-4">
            <Layers className="w-3.5 h-3.5 text-teal-400" />
            <span>Civic Engineering &amp; ML Architecture</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight font-['Space_Grotesk',sans-serif] mb-4">
            About Melbourne Pulse
          </h1>
          <p className="text-base sm:text-lg text-slate-300 leading-relaxed max-w-2xl">
            A zero-cost, open-source civic analytics platform that streams live pedestrian and parking telemetry across Melbourne&apos;s CBD, powered by LightGBM machine learning and automated on serverless infrastructure.
          </p>
        </div>

        {/* 1. Architecture Flow */}
        <section className="space-y-6">
          <div className="flex items-center gap-2 text-teal-400 font-mono text-xs font-semibold uppercase tracking-wider">
            <Cpu className="w-4 h-4" />
            <span>End-to-End System Design</span>
          </div>
          <h2 className="text-2xl font-bold text-white font-['Space_Grotesk',sans-serif]">
            Architecture Pipeline
          </h2>

          <div className="p-6 rounded-2xl bg-[#0d1424]/80 border border-white/10 backdrop-blur-xl space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/80 border border-white/5 space-y-2">
                <span className="text-[11px] font-mono text-teal-400 font-bold block">01. INGEST</span>
                <h3 className="font-semibold text-white text-sm">Open Data Portals</h3>
                <p className="text-xs text-slate-400">
                  City of Melbourne Opendatasoft API (per-minute pedestrian streams + 6,324 bay sensors).
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-white/5 space-y-2">
                <span className="text-[11px] font-mono text-teal-400 font-bold block">02. PIPELINE</span>
                <h3 className="font-semibold text-white text-sm">GitHub Actions</h3>
                <p className="text-xs text-slate-400">
                  Runs hourly at :07. Executes pytest suite before database write, aggregates hourly counts.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-white/5 space-y-2">
                <span className="text-[11px] font-mono text-teal-400 font-bold block">03. DATABASE</span>
                <h3 className="font-semibold text-white text-sm">Neon Postgres</h3>
                <p className="text-xs text-slate-400">
                  Sydney region. 0.25 CU serverless compute scaling to zero after 5m. 90-day retention window.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-white/5 space-y-2">
                <span className="text-[11px] font-mono text-teal-400 font-bold block">04. FRONTEND</span>
                <h3 className="font-semibold text-white text-sm">Next.js on Vercel</h3>
                <p className="text-xs text-slate-400">
                  Server components read Neon via read-only role. Cached hourly, on-demand revalidation.
                </p>
              </div>
            </div>

            {/* ASCII / Visual Flow */}
            <div className="p-4 rounded-xl bg-black/50 border border-white/5 font-mono text-xs text-slate-400 overflow-x-auto leading-relaxed">
              <pre className="text-teal-300">
{`City of Melbourne Open Data ──► GitHub Actions (hourly, :07) ──► Neon Postgres ◄── Next.js on Vercel
  parking bay sensors              pytest (gate)                 hourly aggregates    (read-only role,
  pedestrian counts                fetch.py  → aggregates                             ISR, revalidate
  sensor locations                 summary.py → Gemini Flash                          on demand)
                                   POST /api/revalidate ────────────────────────────►`}
              </pre>
            </div>
          </div>
        </section>

        {/* 2. Machine Learning Model Evaluation */}
        <section className="space-y-6">
          <div className="flex items-center gap-2 text-purple-400 font-mono text-xs font-semibold uppercase tracking-wider">
            <Brain className="w-4 h-4" />
            <span>Empirical Evaluation</span>
          </div>
          <h2 className="text-2xl font-bold text-white font-['Space_Grotesk',sans-serif]">
            Forecast Model Benchmark
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            The model was tested strictly on 8 weeks of unseen test data (2026-08-05 to 2026-09-29) spanning 132,696 sensor-hours across 103 Melbourne counting stations.
          </p>

          {/* Results Table */}
          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#0d1424]/80 backdrop-blur-xl">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead className="border-b border-white/10 bg-white/5 text-slate-400 font-mono text-xs">
                <tr>
                  <th className="p-4 font-semibold">Method</th>
                  <th className="p-4 font-semibold text-right">Average Error (MAE, people/hr)</th>
                  <th className="p-4 font-semibold text-right">Average % Error (MAPE)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                <tr className="hover:bg-white/5 transition-colors">
                  <td className="p-4 text-slate-300 font-sans">Seasonal Naive (same hour last week)</td>
                  <td className="p-4 text-right text-slate-400">71.5</td>
                  <td className="p-4 text-right text-slate-400">31.6%</td>
                </tr>
                <tr className="hover:bg-white/5 transition-colors">
                  <td className="p-4 text-slate-300 font-sans">Typical Baseline (8-week median)</td>
                  <td className="p-4 text-right text-slate-400">61.7</td>
                  <td className="p-4 text-right text-slate-400">25.7%</td>
                </tr>
                <tr className="bg-purple-500/10 hover:bg-purple-500/15 transition-colors font-bold text-purple-200">
                  <td className="p-4 font-sans flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-purple-400" />
                    LightGBM (Our Model)
                  </td>
                  <td className="p-4 text-right text-teal-300">55.3</td>
                  <td className="p-4 text-right text-teal-300">23.6%</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Model Chart Image */}
          <div className="rounded-2xl border border-white/10 overflow-hidden bg-slate-950 p-4 shadow-2xl">
            <div className="relative w-full aspect-[16/9]">
              <Image
                src="/chart.png"
                alt="Actual vs forecast vs typical for three sensors over one test week"
                fill
                className="object-contain"
                priority
              />
            </div>
            <p className="text-xs text-slate-400 mt-3 text-center">
              Actual vs LightGBM forecast vs 8-week typical baseline across Town Hall (West), Flinders La-Swanston St, and QV2 Swanston Street.
            </p>
          </div>

          {/* Honest Grand Final Friday Note */}
          <div className="p-5 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex gap-4 items-start">
            <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-1.5 text-xs sm:text-sm text-amber-200/90 leading-relaxed">
              <h3 className="font-semibold text-amber-100">
                The Honest Grand Final Friday Note
              </h3>
              <p>
                The test period includes the Victorian public holiday for Friday before the AFL Grand Final. The model correctly identifies calendar public holidays, but because most regular public holidays make the CBD quieter, machine learning models cannot anticipate major unexpected sports parades or surge events that pull thousands of pedestrians into unexpected corridors. That is where our biggest residuals occur.
              </p>
            </div>
          </div>
        </section>

        {/* 3. Free-Tier Budget Breakdown */}
        <section className="space-y-6">
          <div className="flex items-center gap-2 text-emerald-400 font-mono text-xs font-semibold uppercase tracking-wider">
            <DollarSign className="w-4 h-4" />
            <span>Zero-Dollar Infrastructure</span>
          </div>
          <h2 className="text-2xl font-bold text-white font-['Space_Grotesk',sans-serif]">
            Free-Tier Budget Breakdown
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            The entire pipeline, model inference, database, and front-end run indefinitely within the free tiers of Neon, GitHub Actions, Google Gemini, and Vercel.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Storage Box */}
            <div className="p-6 rounded-2xl bg-[#0d1424]/80 border border-white/10 backdrop-blur-xl space-y-3">
              <h3 className="text-base font-semibold text-white flex items-center justify-between">
                <span>Neon Storage</span>
                <span className="text-xs font-mono text-emerald-400">~40 MB at 90 days</span>
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Aggregated hourly records keep storage footprint to ~114 bytes/row. Rows older than 90 days are pruned automatically. 40 MB represents only <strong>8% of Neon&apos;s 0.5 GB free limit</strong>.
              </p>
            </div>

            {/* Compute Box */}
            <div className="p-6 rounded-2xl bg-[#0d1424]/80 border border-white/10 backdrop-blur-xl space-y-3">
              <h3 className="text-base font-semibold text-white flex items-center justify-between">
                <span>Neon Compute</span>
                <span className="text-xs font-mono text-emerald-400">~18 CU-hours / mo</span>
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Compute scales to zero after 5 minutes of inactivity. Fixed at 0.25 CU minimum size. Website requests hit the cached ISR layer and do not wake the DB. Uses <strong>~18% of the 100 CU-hour quota</strong>.
              </p>
            </div>
          </div>
        </section>

        {/* 4. Data Provenance & Author */}
        <section className="pt-6 border-t border-white/10 space-y-4 text-xs text-slate-400 leading-relaxed">
          <p>
            <strong>Data License:</strong> Telemetry is sourced from the{" "}
            <a
              href="https://data.melbourne.vic.gov.au"
              target="_blank"
              rel="noreferrer"
              className="text-slate-200 underline hover:text-teal-400 transition-colors"
            >
              City of Melbourne Open Data
            </a>{" "}
            platform under Creative Commons Attribution (CC BY).
          </p>
          <p>
            Developed by <strong>Rukshan Dias</strong> · Data Science, Deakin University. View complete source code, test suites, and model training scripts on{" "}
            <a
              href="https://github.com/Ruki-Diaz/melbourne-pulse"
              target="_blank"
              rel="noreferrer"
              className="text-teal-400 hover:text-teal-300 underline transition-colors"
            >
              GitHub
            </a>.
          </p>
        </section>
      </div>
    </main>
  );
}
