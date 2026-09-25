// What frames every video of the brand: captions of what is being said, and a progress line.
import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { useScale } from "./scale";
import { color, font } from "./tokens";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// About this many characters of caption fit across the box on one row.
const CAPTION_CHARS = 24;

// Splits a line into rows that each fit, keeping each word's position in the line.
const rows = (words: string[]) => {
  const result: number[][] = [[]];
  let used = 0;
  words.forEach((word, i) => {
    const row = result[result.length - 1];
    if (row.length > 0 && used + 1 + word.length > CAPTION_CHARS) {
      result.push([i]);
      used = word.length;
    } else {
      row.push(i);
      used += (row.length > 1 ? 1 : 0) + word.length;
    }
  });
  return result;
};

// The line being said, one row at a time, the word being said now in the accent colour.
// Words are spread evenly over `length` frames from `start`.
export const Caption: React.FC<{ text: string; start: number; length: number }> = ({ text, start, length }) => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  const s = useScale();
  const words = text.split(" ");
  const spoken = interpolate(frame, [start, start + length], [0, words.length], clamp);
  const now = Math.min(words.length - 1, Math.floor(spoken));
  const row = rows(words).find((r) => r.includes(now))!;
  return (
    <div
      style={{
        position: "absolute", left: 0, right: 0, top: height * 0.72, display: "flex", justifyContent: "center",
        opacity: interpolate(frame, [start - 4, start + 2], [0, 1], clamp),
      }}
    >
      <div
        style={{
          fontFamily: font.body, fontSize: 50 * s, whiteSpace: "pre", color: color.ink, background: color.paper,
          border: `${4 * s}px solid ${color.ink}`, borderRadius: 22 * s, padding: `${14 * s}px ${30 * s}px`,
        }}
      >
        {row.map((index, i) => (
          <span key={index} style={{ color: index === now ? color.accent : index < now ? color.ink : color.inkSoft }}>
            {i > 0 ? " " : ""}
            {words[index]}
          </span>
        ))}
      </div>
    </div>
  );
};

export const Progress: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <div
      style={{
        position: "absolute", top: 0, left: 0, height: 10 * useScale(), background: color.accent,
        width: `${(frame / durationInFrames) * 100}%`,
      }}
    />
  );
};
