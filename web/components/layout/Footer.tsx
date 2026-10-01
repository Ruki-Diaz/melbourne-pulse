import React from "react";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { GithubIcon } from "@/components/icons";

export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-[#03060a] text-slate-400 py-12 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex flex-col items-center md:items-start text-center md:text-left gap-1">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white font-['Space_Grotesk',sans-serif] tracking-tight">
              MELBOURNE<span className="text-teal-400 ml-1">PULSE</span>
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800 text-slate-400">
              Live Civic Analytics
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Data:{" "}
            <a
              href="https://data.melbourne.vic.gov.au"
              target="_blank"
              rel="noreferrer"
              className="text-slate-300 hover:text-teal-400 underline underline-offset-2 transition-colors"
            >
              City of Melbourne Open Data (CC BY)
            </a>{" "}
            · Source on{" "}
            <a
              href="https://github.com/Ruki-Diaz/melbourne-pulse"
              target="_blank"
              rel="noreferrer"
              className="text-slate-300 hover:text-teal-400 underline underline-offset-2 transition-colors"
            >
              GitHub
            </a>
          </p>
        </div>

        {/* Links */}
        <div className="flex items-center gap-6 text-xs text-slate-400">
          <Link href="/" className="hover:text-teal-300 transition-colors">
            Home
          </Link>
          <Link href="/map" className="hover:text-teal-300 transition-colors">
            Live Map
          </Link>
          <Link href="/about" className="hover:text-teal-300 transition-colors">
            About &amp; Model
          </Link>
          <a
            href="https://github.com/Ruki-Diaz/melbourne-pulse"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 hover:text-teal-300 transition-colors"
          >
            <GithubIcon className="w-3.5 h-3.5" />
            <span>GitHub</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </footer>
  );
}
