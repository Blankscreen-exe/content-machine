// Hand-drawn shapes: boxes with rough borders and loose arrows that draw themselves.
// Rough.js draws the wobble; a fixed seed per shape keeps it identical from frame to frame.
import React from "react";
import rough from "roughjs";
import { useVideoConfig } from "remotion";
import { useScale } from "./scale";
import { color, font } from "./tokens";

const gen = rough.generator();

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

const roundedRect = (x: number, y: number, w: number, h: number, r: number) =>
  `M${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} ` +
  `H${x + r} Q${x},${y + h} ${x},${y + h - r} V${y + r} Q${x},${y} ${x + r},${y} Z`;

// A path that draws itself as `progress` goes from 0 to 1.
const DrawnPath: React.FC<{ d: string; stroke: string; width: number; progress: number }> = ({ d, stroke, width, progress }) => (
  <path
    d={d} stroke={stroke} strokeWidth={width} fill="none" strokeLinecap="round" strokeLinejoin="round"
    pathLength={1} strokeDasharray={1} strokeDashoffset={1 - clamp01(progress)}
  />
);

// A labelled box that lands and draws its border as `enter` goes from 0 to 1.
// Position and size are in kit units (see scale.ts).
export const SketchBox: React.FC<{
  x: number; y: number; w: number; h: number; lines: string[]; enter: number; seed: number; size?: number;
}> = ({ x, y, w, h, lines, enter, seed, size = 40 }) => {
  const s = useScale();
  const pad = 12;
  const border = gen.toPaths(
    gen.path(roundedRect(pad, pad, w * s, h * s, 22 * s), { stroke: color.ink, strokeWidth: 4, roughness: 1.1, bowing: 1.5, seed }),
  );
  return (
    <div
      style={{
        position: "absolute", left: x * s, top: y * s, width: w * s, height: h * s,
        opacity: clamp01(enter * 1.6), transform: `scale(${0.88 + 0.12 * Math.min(enter, 1.05)})`,
      }}
    >
      <div style={{ position: "absolute", inset: 4, borderRadius: 20 * s, background: color.accentSoft }} />
      <svg width={w * s + 2 * pad} height={h * s + 2 * pad} style={{ position: "absolute", left: -pad, top: -pad, overflow: "visible" }}>
        {border.map((p, i) => <DrawnPath key={i} d={p.d} stroke={color.ink} width={p.strokeWidth} progress={enter} />)}
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        {lines.map((line) => (
          <span key={line} style={{ fontFamily: font.body, fontSize: size * s, color: color.ink }}>{line}</span>
        ))}
      </div>
    </div>
  );
};

type Point = [number, number];

// A thin arrow along a curve, in kit units, whose head appears once the line arrives.
export const HandArrow: React.FC<{ from: Point; c1: Point; c2: Point; to: Point; progress: number }> = ({
  from, c1, c2, to, progress,
}) => {
  const s = useScale();
  const { width, height } = useVideoConfig();
  const [a, b, c, d] = [from, c1, c2, to].map(([px, py]) => [px * s, py * s]);
  const angle = Math.atan2(d[1] - c[1], d[0] - c[0]);
  const head = 20 * s;
  const wing = (turn: number) => [d[0] - head * Math.cos(angle + turn), d[1] - head * Math.sin(angle + turn)];
  const [left, right] = [wing(0.5), wing(-0.5)];
  return (
    <svg width={width} height={height} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
      <DrawnPath d={`M${a} C${b} ${c} ${d}`} stroke={color.inkSoft} width={3.5 * s} progress={progress} />
      <DrawnPath d={`M${left} L${d} L${right}`} stroke={color.inkSoft} width={3.5 * s} progress={(progress - 0.85) / 0.15} />
    </svg>
  );
};
