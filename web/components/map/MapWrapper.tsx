"use client";

import dynamic from "next/dynamic";
import React from "react";
import type { MapSensorItem, MapParkingItem } from "./LiveLeafletMap";

const DynamicLeafletMap = dynamic(
  () => import("./LiveLeafletMap").then((mod) => mod.LiveLeafletMap),
  {
    ssr: false,
    loading: () => (
      <div className="relative w-full h-[calc(100vh-4rem)] flex items-center justify-center bg-[#05080D]">
        <div className="flex flex-col items-center gap-3">
          <div className="relative flex h-10 w-10">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-10 w-10 bg-teal-500/30 border border-teal-400"></span>
          </div>
          <p className="text-xs font-mono text-teal-300 animate-pulse">
            Loading Melbourne Live Map telemetry...
          </p>
        </div>
      </div>
    ),
  }
);

interface MapWrapperProps {
  sensors: MapSensorItem[];
  parking: MapParkingItem[];
  summaryText?: string;
  updatedMinutesAgo: number;
  isStale: boolean;
  forecastsBySensor: Record<number, Array<{ hourLabel: string; forecast: number; typical: number }>>;
  historyBySensor: Record<number, Array<{ hourLabel: string; actual: number }>>;
}

export function MapWrapper(props: MapWrapperProps) {
  return <DynamicLeafletMap {...props} />;
}
