"use client";

import React, { useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";

export interface GlassHeadlineHeroProps {
  eyebrow?: string;
  title?: string;
  description?: string;
  primaryAction?: { label: string; href: string };
  secondaryAction?: { label: string; href: string };
  colors?: string[];
  className?: string;
}

export function GlassHeadlineHero({
  eyebrow = "Live · updated 5 min ago",
  title = "Melbourne, live.",
  description = "See how busy the CBD is right now, and what the next 24 hours look like.",
  primaryAction = { label: "Open the live map", href: "/map" },
  secondaryAction = { label: "How it works", href: "#how" },
  colors = ["#05080D", "#00E5C7", "#2F6BFF", "#7C3AED", "#D6FFF7"],
  className = "",
}: GlassHeadlineHeroProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    if (shouldReduceMotion) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl2", { alpha: true, antialias: true, powerPreference: "high-performance" });
    if (!gl) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || window.innerWidth);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 640);

    const vsSource = `#version 300 es
      in vec2 position;
      out vec2 uv;
      void main() {
        uv = position * 0.5 + 0.5;
        gl_Position = vec4(position, 0.0, 1.0);
      }
    `;

    const fsSource = `#version 300 es
      precision highp float;
      in vec2 uv;
      out vec4 fragColor;
      uniform float u_time;
      uniform vec2 u_resolution;
      uniform vec2 u_mouse;

      // Hex RGB helpers
      vec3 col1 = vec3(0.02, 0.03, 0.05); // #05080D
      vec3 col2 = vec3(0.0, 0.898, 0.78);  // #00E5C7 (Teal)
      vec3 col3 = vec3(0.184, 0.42, 1.0);  // #2F6BFF (Blue)
      vec3 col4 = vec3(0.486, 0.227, 0.93); // #7C3AED (Purple)

      float hash(vec2 p) {
        return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
      }

      float noise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
                   mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
      }

      float fbm(vec2 p) {
        float v = 0.0;
        float a = 0.5;
        vec2 shift = vec2(100.0);
        mat2 rot = mat2(cos(0.5), sin(0.5), -sin(0.5), cos(0.5));
        for (int i = 0; i < 4; ++i) {
          v += a * noise(p);
          p = rot * p * 2.0 + shift;
          a *= 0.5;
        }
        return v;
      }

      void main() {
        vec2 st = (gl_FragCoord.xy * 2.0 - u_resolution.xy) / min(u_resolution.x, u_resolution.y);
        float t = u_time * 0.15;
        
        vec2 q = vec2(fbm(st + vec2(0.0, t * 0.4)), fbm(st + vec2(5.2, 1.3)));
        vec2 r = vec2(fbm(st + 4.0 * q + vec2(1.7, 9.2) + t * 0.2), fbm(st + 4.0 * q + vec2(8.3, 2.8) - t * 0.15));

        float f = fbm(st + 4.0 * r);

        vec3 color = mix(col1, col3, clamp((f * f) * 4.0, 0.0, 1.0));
        color = mix(color, col2, clamp(length(q) * 0.9, 0.0, 1.0));
        color = mix(color, col4, clamp(length(r.x) * 0.7, 0.0, 1.0));

        // Glass chromatic aberration / refraction shimmer
        float vignette = 1.0 - smoothstep(0.4, 1.4, length(st));
        color *= (f * f * f + 0.6 * f * f + 0.5 * f);
        color *= vignette;

        // Subtle electric teal pulse
        color += col2 * 0.15 * pow(max(0.0, 1.0 - length(st - vec2(0.0, 0.2))), 3.0);

        fragColor = vec4(color * 0.85, 0.95);
      }
    `;

    function compileShader(type: number, src: string) {
      const shader = gl!.createShader(type);
      if (!shader) return null;
      gl!.shaderSource(shader, src);
      gl!.compileShader(shader);
      if (!gl!.getShaderParameter(shader, gl!.COMPILE_STATUS)) {
        console.warn(gl!.getShaderInfoLog(shader));
        gl!.deleteShader(shader);
        return null;
      }
      return shader;
    }

    const vs = compileShader(gl.VERTEX_SHADER, vsSource);
    const fs = compileShader(gl.FRAGMENT_SHADER, fsSource);
    if (!vs || !fs) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.warn(gl.getProgramInfoLog(program));
      return;
    }

    const posBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW
    );

    const posAttrib = gl.getAttribLocation(program, "position");
    const uTime = gl.getUniformLocation(program, "u_time");
    const uRes = gl.getUniformLocation(program, "u_resolution");
    const uMouse = gl.getUniformLocation(program, "u_mouse");

    const mouseX = width / 2;
    const mouseY = height / 2;

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
      gl.viewport(0, 0, width, height);
    };

    window.addEventListener("resize", handleResize);

    const startTime = performance.now();

    const render = () => {
      const currentTime = (performance.now() - startTime) * 0.001;
      gl.viewport(0, 0, width, height);
      gl.useProgram(program);

      gl.enableVertexAttribArray(posAttrib);
      gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer);
      gl.vertexAttribPointer(posAttrib, 2, gl.FLOAT, false, 0, 0);

      gl.uniform1f(uTime, currentTime);
      gl.uniform2f(uRes, width, height);
      gl.uniform2f(uMouse, mouseX, mouseY);

      gl.drawArrays(gl.TRIANGLES, 0, 6);
      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
      if (posBuffer) gl.deleteBuffer(posBuffer);
      if (program) gl.deleteProgram(program);
    };
  }, [shouldReduceMotion]);

  // Use configured colors if needed
  const baseBg = colors[0] || "#05080D";

  return (
    <div
      style={{ backgroundColor: baseBg }}
      className={`relative min-h-[580px] md:min-h-[640px] w-full flex flex-col justify-center items-center overflow-hidden ${className}`}
    >
      {/* Dynamic WebGL2 Glass Canvas */}
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className="absolute inset-0 w-full h-full object-cover pointer-events-none opacity-80"
      />

      {/* Atmospheric Glass Glow Overlays */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(0,229,199,0.12),transparent_60%)] pointer-events-none"
      />
      <div
        aria-hidden="true"
        className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-[#05080D] to-transparent pointer-events-none"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 backdrop-blur-[1px] pointer-events-none"
      />

      {/* Content Container */}
      <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 text-center flex flex-col items-center pt-8 pb-16">
        {/* Eyebrow badge */}
        {eyebrow && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-teal-950/60 border border-teal-500/30 text-teal-300 text-xs sm:text-sm font-medium tracking-wide mb-6 backdrop-blur-md shadow-[0_0_20px_rgba(0,229,199,0.15)]"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-400"></span>
            </span>
            <span>{eyebrow}</span>
          </motion.div>
        )}

        {/* Hero Title */}
        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white mb-6 font-['Space_Grotesk',sans-serif]"
        >
          <span className="bg-clip-text text-transparent bg-gradient-to-b from-white via-slate-100 to-slate-400">
            {title}
          </span>
        </motion.h1>

        {/* AI Summary / Description */}
        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-base sm:text-lg md:text-xl text-slate-300 max-w-2xl mx-auto leading-relaxed mb-10 font-normal"
        >
          {description}
        </motion.p>

        {/* Action Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-wrap items-center justify-center gap-4 w-full sm:w-auto"
        >
          {primaryAction && (
            <Link
              href={primaryAction.href}
              className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-teal-400 to-cyan-400 text-zinc-950 hover:from-teal-300 hover:to-cyan-300 transition-all duration-200 shadow-[0_0_25px_rgba(0,229,199,0.35)] hover:shadow-[0_0_35px_rgba(0,229,199,0.55)] hover:scale-[1.02] active:scale-[0.98]"
            >
              <span>{primaryAction.label}</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          )}

          {secondaryAction && (
            <Link
              href={secondaryAction.href}
              className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-medium text-sm text-slate-200 bg-slate-900/60 hover:bg-slate-800/80 border border-slate-700/60 hover:border-slate-500/60 backdrop-blur-md transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
            >
              <span>{secondaryAction.label}</span>
            </Link>
          )}
        </motion.div>
      </div>
    </div>
  );
}

export default GlassHeadlineHero;
