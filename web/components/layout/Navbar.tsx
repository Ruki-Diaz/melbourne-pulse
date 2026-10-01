"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Map, CalendarClock, Info, Menu, X } from "lucide-react";
import { GithubIcon } from "@/components/icons";

export function Navbar() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { href: "/", label: "Home", icon: Activity },
    { href: "/map", label: "Live Map", icon: Map },
    { href: "/plan", label: "Plan", icon: CalendarClock },
    { href: "/about", label: "About", icon: Info },
  ];

  return (
    <header className="sticky top-0 z-50 w-full bg-[#05080D]/80 backdrop-blur-xl border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/30 group-hover:border-teal-400/70 transition-colors">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-teal-400"></span>
            </span>
          </div>
          <span className="font-bold tracking-tight text-white font-['Space_Grotesk',sans-serif] text-base sm:text-lg">
            MELBOURNE<span className="text-teal-400 ml-1">PULSE</span>
          </span>
        </Link>

        {/* Desktop Nav Links */}
        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? "bg-white/10 text-teal-300 shadow-sm border border-white/10"
                    : "text-slate-300 hover:text-white hover:bg-white/5"
                }`}
              >
                <Icon className="w-4 h-4 text-teal-400" />
                <span>{link.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right Action: GitHub repo */}
        <div className="hidden md:flex items-center gap-3">
          <Link
            href="https://github.com/Ruki-Diaz/melbourne-pulse"
            target="_blank"
            rel="noreferrer"
            aria-label="GitHub Repository"
            className="p-2 rounded-lg bg-slate-900 border border-slate-700/80 text-slate-300 hover:text-white hover:border-teal-400 transition-colors"
          >
            <GithubIcon className="w-4 h-4" />
          </Link>
          <Link
            href="/map"
            className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-teal-400 text-zinc-950 hover:bg-teal-300 transition-all shadow-[0_0_15px_rgba(0,229,199,0.3)]"
          >
            Live Map
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          type="button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="md:hidden p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5"
          aria-label="Toggle menu"
        >
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-white/10 bg-[#05080D]/95 backdrop-blur-2xl px-4 py-4 space-y-2">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-medium ${
                  isActive
                    ? "bg-teal-500/10 text-teal-300 border border-teal-500/20"
                    : "text-slate-300 hover:text-white hover:bg-white/5"
                }`}
              >
                <Icon className="w-4 h-4 text-teal-400" />
                <span>{link.label}</span>
              </Link>
            );
          })}
          <div className="pt-2 border-t border-white/10 flex items-center justify-between">
            <Link
              href="https://github.com/Ruki-Diaz/melbourne-pulse"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 text-xs text-slate-400 hover:text-teal-300"
            >
              <GithubIcon className="w-4 h-4" />
              <span>GitHub Source</span>
            </Link>
            <Link
              href="/map"
              onClick={() => setMobileMenuOpen(false)}
              className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-teal-400 text-zinc-950"
            >
              Open Live Map
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
