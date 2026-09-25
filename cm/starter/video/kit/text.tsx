// The kit's type: bold headlines whose words rise in turn, body text that types itself,
// and side notes that write themselves on.
import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { useScale } from "./scale";
import { color, font } from "./tokens";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Word: React.FC<{ text: string; accent: boolean; delay: number }> = ({ text, accent, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame: frame - delay, fps, config: { damping: 15, mass: 0.6 } });
  return (
    <span
      style={{
        display: "inline-block", marginRight: "0.25em", color: accent ? color.accent : color.ink,
        opacity: Math.min(1, enter * 1.5), transform: `translateY(${(1 - enter) * 0.45}em)`,
      }}
    >
      {text}
    </span>
  );
};

// Words listed in `accent` (without their punctuation) take the accent colour.
export const Headline: React.FC<{
  text: string; accent?: string[]; size?: number; delay?: number; stagger?: number; style?: React.CSSProperties;
}> = ({ text, accent = [], size = 110, delay = 0, stagger = 4, style }) => {
  const scale = useScale();
  return (
    <div style={{ fontFamily: font.head, fontWeight: 800, fontSize: size * scale, lineHeight: 1.08, ...style }}>
      {text.split(" ").map((word, i) => (
        <Word key={i} text={word} accent={accent.includes(word.replace(/[.,!?]/g, ""))} delay={delay + i * stagger} />
      ))}
    </div>
  );
};

// Body text typed out between two frames of the scene it is in.
export const TypeOn: React.FC<{ text: string; start: number; end: number; size?: number; style?: React.CSSProperties }> = ({
  text, start, end, size = 46, style,
}) => {
  const frame = useCurrentFrame();
  const scale = useScale();
  const count = Math.floor(interpolate(frame, [start, end], [0, text.length], clamp));
  return (
    <div style={{ fontFamily: font.body, fontSize: size * scale, lineHeight: 1.45, color: color.ink, ...style }}>
      {text.slice(0, count)}
    </div>
  );
};

// A side note, tilted, revealed left to right as `progress` goes from 0 to 1.
export const Note: React.FC<{ text: string; x: number; y: number; progress: number; size?: number; rotate?: number }> = ({
  text, x, y, progress, size = 60, rotate = -5,
}) => {
  const scale = useScale();
  const hidden = (1 - Math.min(1, Math.max(0, progress))) * 100;
  return (
    <div
      style={{
        position: "absolute", left: x * scale, top: y * scale, fontFamily: font.body, fontSize: size * scale,
        color: color.inkSoft, transform: `rotate(${rotate}deg)`, whiteSpace: "nowrap",
        // room past the text box, so the reveal never clips a slanted last letter
        padding: "0 0.3em", margin: "0 -0.3em",
        clipPath: `inset(-20% ${hidden}% -20% 0)`,
      }}
    >
      {text}
    </div>
  );
};
