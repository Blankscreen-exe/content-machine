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

// A word of the script and the frames it is said over, from the start of its scene: what
// the app hands a scene when its captions are timed to the voice.
type TimedWord = { text: string; from: number; to: number };

// The line being said, one row at a time; the word being said now is picked out. Timed to
// the voice when `words` is given; otherwise the script is spread over `length` frames from
// `start`, as before there is a take.
export const Caption: React.FC<{ text: string; start: number; length: number; words?: TimedWord[] | null }> = ({
  text, start, length, words: timed,
}) => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  const s = useScale();
  const words = timed?.length ? timed.map((word) => word.text) : text.split(" ");
  const appear = timed?.length ? timed[0].from : start;
  const now = timed?.length
    ? Math.max(0, timed.filter((word) => word.from <= frame).length - 1)   // the last word begun
    : Math.min(words.length - 1, Math.floor(interpolate(frame, [start, start + length], [0, words.length], clamp)));
  const row = rows(words).find((r) => r.includes(now))!;
  return (
    <div
      style={{
        position: "absolute", left: 0, right: 0, top: height * 0.72, display: "flex", justifyContent: "center",
        opacity: interpolate(frame, [appear - 4, appear + 2], [0, 1], clamp),
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

// A scene as the app hands it, as far as captions need.
type CaptionedScene = { from: number; duration: number; speech: number; script: string; words: TimedWord[] | null };

// How long a line stays up after its last word, when no line follows at once.
const LINGER_SECONDS = 1.5;

// All of a video's captions, placed once over the whole of it. Timed to the voice when the
// scenes carry words: each line comes up with its first word and stays until the next line
// begins, or a moment after its last word, whatever the pictures under it do. Before there
// is a take, each scene's script is spread over its speech, within the scene.
export const Captions: React.FC<{ scenes: CaptionedScene[] }> = ({ scenes }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lines = scenes
    .filter((scene) => scene.words?.length)
    .map((scene) => scene.words!.map((word) => ({ ...word, from: scene.from + word.from, to: scene.from + word.to })));
  if (lines.length) {
    const current = lines.filter((line) => line[0].from - 4 <= frame).at(-1);
    if (!current || frame > current[current.length - 1].from + LINGER_SECONDS * fps) return null;
    return <Caption text="" start={0} length={0} words={current} />;
  }
  const scene = scenes.find((s) => s.speech > 0 && frame >= s.from && frame < s.from + s.duration);
  return scene ? <Caption text={scene.script} start={scene.from} length={scene.speech} /> : null;
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
