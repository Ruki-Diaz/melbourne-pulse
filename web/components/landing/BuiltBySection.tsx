"use client";

import React from "react";
import { motion } from "framer-motion";
import { Globe, User, GraduationCap } from "lucide-react";
import { GithubIcon, LinkedinIcon } from "@/components/icons";
import Link from "next/link";

export function BuiltBySection() {
  return (
    <section className="py-20 max-w-6xl mx-auto px-4 sm:px-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="p-8 sm:p-10 rounded-2xl bg-gradient-to-r from-[#0d1424] via-[#0b101c] to-[#080d17] border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-center justify-between gap-6 shadow-2xl"
      >
        <div className="flex items-center gap-5 text-center md:text-left">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-teal-500/20 to-blue-500/20 border border-teal-500/30 flex items-center justify-center text-teal-300 shrink-0 shadow-[0_0_20px_rgba(0,229,199,0.15)]">
            <User className="w-8 h-8" />
          </div>
          <div>
            <div className="flex items-center justify-center md:justify-start gap-2 text-xs font-mono text-teal-400 mb-1">
              <GraduationCap className="w-3.5 h-3.5" />
              <span>Creator &amp; Maintainer</span>
            </div>
            <h3 className="text-xl sm:text-2xl font-bold text-white font-['Space_Grotesk',sans-serif]">
              Rukshan Dias
            </h3>
            <p className="text-sm text-slate-400">Data Science · Deakin University</p>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            href="https://github.com/Ruki-Diaz"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:border-teal-400 text-slate-200 hover:text-white text-xs font-medium transition-all duration-200 hover:scale-[1.03]"
          >
            <GithubIcon className="w-4 h-4 text-teal-400" />
            <span>GitHub Profile</span>
          </Link>

          <Link
            href="https://rukshandias.vercel.app"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:border-teal-400 text-slate-200 hover:text-white text-xs font-medium transition-all duration-200 hover:scale-[1.03]"
          >
            <Globe className="w-4 h-4 text-cyan-400" />
            <span>Portfolio</span>
          </Link>

          {/* LinkedIn profile */}
          <a
            href="https://www.linkedin.com/in/rukshan-dias-a088921a6/?isSelfProfile=true"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900/60 border border-slate-700/50 hover:border-blue-400 text-slate-300 hover:text-white text-xs font-medium transition-all duration-200 hover:scale-[1.03]"
          >
            <LinkedinIcon className="w-4 h-4 text-blue-400" />
            <span>LinkedIn</span>
          </a>
        </div>
      </motion.div>
    </section>
  );
}
