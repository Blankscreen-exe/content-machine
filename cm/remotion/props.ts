// Written by Content Machine into the workspace before every render; do not edit.
//
// What the app hands a piece's video when it renders it. A piece's `video/Video.tsx`
// exports `Video`, a component that takes these props and draws the whole video with its
// brand's kit. Lengths and positions are in frames.
// A script word, and when it is said: frames from the start of its scene, which can fall
// outside the scene when a line runs past its picture. `to` is when the next word starts.
export type Word = { text: string; from: number; to: number };

export type Scene = {
  title: string;
  from: number;       // the frame it comes on at
  duration: number;   // how many frames it stays on
  speech: number;     // how many frames, from its first, its script takes to say
  script: string;
  onScreen: string;
  animation: string;
  // When the captions are timed to a take: the script's words as said. Otherwise null,
  // and a caption spreads the script over `speech`.
  words: Word[] | null;
};

// The voice and music are played by the app, under the video; a video never plays them.
export type Voice = {
  src: string;               // a file beside the render, for staticFile()
  from: number;              // the frame it starts at
  trimBefore: number;        // frames skipped at the take's start
  trimAfter: number | null;  // the frame of the take it stops at, or its end
  volume: number;
};

export type Music = {
  src: string;
  volume: number;
};

export type VideoProps = {
  fps: number;
  width: number;
  height: number;
  total: number;      // frames in the whole video
  captions: boolean;
  scenes: Scene[];
  voice: Voice | null;
  music: Music | null;
};
