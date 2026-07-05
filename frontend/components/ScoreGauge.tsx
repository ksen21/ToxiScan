"use client";

import { useEffect, useState } from "react";
import { toneForLabel } from "@/lib/tone";

interface ScoreGaugeProps {
  scoreOutOf10: number;
  label: string;
}

const CX = 110;
const CY = 108;
const R = 88;

function angleForScore(score: number): number {
  // 0 -> 180deg (far left), 10 -> 0deg (far right), sweeping over the top
  const clamped = Math.min(10, Math.max(0, score));
  return 180 - (clamped / 10) * 180;
}

function pointAt(angleDeg: number, radius: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return {
    x: CX + radius * Math.cos(rad),
    y: CY - radius * Math.sin(rad),
  };
}

function arcPath(startScore: number, endScore: number, radius: number) {
  const start = pointAt(angleForScore(startScore), radius);
  const end = pointAt(angleForScore(endScore), radius);
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 0 0 ${end.x} ${end.y}`;
}

// Zone boundaries on the 0-10 scale, matching backend score_to_label thresholds
// (85/60/35 out of 100 -> 8.5/6.0/3.5 out of 10)
const ZONES = [
  { from: 0, to: 3.5, color: "#B91C1C" },
  { from: 3.5, to: 6.0, color: "#C2410C" },
  { from: 6.0, to: 8.5, color: "#B45309" },
  { from: 8.5, to: 10, color: "#16794F" },
];

export default function ScoreGauge({ scoreOutOf10, label }: ScoreGaugeProps) {
  const [needleScore, setNeedleScore] = useState(0);
  const tone = toneForLabel(label);

  useEffect(() => {
    // Sweep the needle from zero to the real reading — like an instrument
    // powering on, rather than a static number appearing.
    const raf = requestAnimationFrame(() => setNeedleScore(scoreOutOf10));
    return () => cancelAnimationFrame(raf);
  }, [scoreOutOf10]);

  const needleAngle = angleForScore(needleScore);
  const needleTip = pointAt(needleAngle, R - 16);

  return (
    <div className="flex flex-col items-center">
      <svg
        viewBox="0 0 220 130"
        className="w-full max-w-[260px]"
        role="img"
        aria-label={`Safety reading: ${scoreOutOf10.toFixed(1)} out of 10, ${label}`}
      >
        {ZONES.map((z) => (
          <path
            key={z.from}
            d={arcPath(z.from, z.to, R)}
            fill="none"
            stroke={z.color}
            strokeWidth={10}
            strokeLinecap="round"
            opacity={0.85}
          />
        ))}

        {/* Tick marks at every whole number, like a lab instrument face */}
        {Array.from({ length: 11 }, (_, i) => i).map((tick) => {
          const outer = pointAt(angleForScore(tick), R + 8);
          const inner = pointAt(angleForScore(tick), R - 2);
          return (
            <line
              key={tick}
              x1={inner.x}
              y1={inner.y}
              x2={outer.x}
              y2={outer.y}
              stroke="#8A8D92"
              strokeWidth={1}
            />
          );
        })}

        {/* Needle */}
        <g style={{ transition: "all 0.9s cubic-bezier(0.22, 1, 0.36, 1)" }}>
          <line
            x1={CX}
            y1={CY}
            x2={needleTip.x}
            y2={needleTip.y}
            stroke="#15171A"
            strokeWidth={2.5}
            strokeLinecap="round"
          />
          <circle cx={CX} cy={CY} r={5} fill="#15171A" />
        </g>
      </svg>

      <div className="-mt-2 flex flex-col items-center">
        <span className="font-mono text-4xl font-semibold tabular-nums text-ink">
          {scoreOutOf10.toFixed(1)}
          <span className="text-lg font-medium text-ink-faint">/10</span>
        </span>
        <span
          className={`mt-1 rounded-full border px-3 py-0.5 text-xs font-medium uppercase tracking-wide ${tone.text} ${tone.bg} ${tone.border}`}
        >
          {label}
        </span>
      </div>
    </div>
  );
}
