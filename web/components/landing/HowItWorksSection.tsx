"use client";

import React from "react";
import { motion } from "framer-motion";
import { Radio, Cpu, Database, Sparkles, DollarSign, Layers } from "lucide-react";

export function HowItWorksSection() {
  const steps = [
    {
      step: "01",
      icon: Radio,
      title: "City of Melbourne Sensors",
      badge: "CC BY Open Data",
      description:
        "6,300+ in-ground parking sensors and 100+ optical pedestrian counting stations publishing live minutes.",
    },
    {
      step: "02",
      icon: Cpu,
      title: "Hourly GitHub Action",
      badge: "Automated at :07",
      description:
        "Pytest validation gate prevents corruption, downloads live records, aggregates into clean hourly bins.",
    },
    {
      step: "03",
      icon: Database,
      title: "Neon Serverless Postgres",
      badge: "0.25 CU · 90d",
      description:
        "Serverless storage in Sydney. Scales to zero after 5 idle minutes. Reads protected via read-only role.",
    },
    {
      step: "04",
      icon: Sparkles,
      title: "LightGBM + Gemini Summary",
      badge: "AI Inference",
      description:
        "LightGBM forecasts the next 24 hours with zero future leakage while Gemini Flash generates natural summaries.",
    },
  ];

  return (
    <section id="how" className="py-24 max-w-6xl mx-auto px-4 sm:px-6 scroll-mt-12">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-4">
        <div>
          <div className="flex items-center gap-2 text-teal-400 font-mono text-xs font-semibold uppercase tracking-wider mb-2">
            <Layers className="w-4 h-4" />
            <span>Architecture &amp; Pipeline</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-bold text-white font-['Space_Grotesk',sans-serif]">
            How It Works
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-xl">
            From physical sensors on Swanston Street to your browser in sub-seconds.
          </p>
        </div>

        {/* Runs on $0 Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 font-mono text-xs font-semibold backdrop-blur-md shadow-[0_0_20px_rgba(16,185,129,0.2)]">
          <DollarSign className="w-4 h-4 text-emerald-400" />
          <span>Runs on $0 / Month · 100% Free Tiers</span>
        </div>
      </div>

      {/* 4 Steps Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {steps.map((item, idx) => {
          const Icon = item.icon;
          return (
            <motion.div
              key={item.step}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: idx * 0.1 }}
              className="relative p-6 rounded-2xl bg-[#0d1424]/80 border border-white/10 hover:border-teal-500/40 backdrop-blur-xl transition-all duration-300 flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-mono font-bold text-slate-500 group-hover:text-teal-400 transition-colors">
                    {item.step}
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-white/5 text-slate-300 border border-white/10">
                    {item.badge}
                  </span>
                </div>

                <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300 flex items-center justify-center mb-4 group-hover:scale-110 group-hover:bg-teal-500/20 transition-all duration-200">
                  <Icon className="w-5 h-5" />
                </div>

                <h3 className="text-base font-semibold text-white mb-2 font-['Space_Grotesk',sans-serif]">
                  {item.title}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {item.description}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
