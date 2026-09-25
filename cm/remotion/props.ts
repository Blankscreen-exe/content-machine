// Written by Content Machine into the workspace before every render; do not edit.
//
// What the app hands a piece's video when it renders it. A piece's `video/Video.tsx`
// exports `Video`, a component that takes these props and draws the whole video with its
// brand's kit. Lengths and positions are in frames.
export type Scene = {
  title: string;
  from: number;       // the frame it comes on at
  duration: number;   // how many frames it stays on
  speech: number;     // how many frames, from its first, its script takes to say
  script: string;
  onScreen: string;
  animation: string;
};

export type VideoProps = {
  fps: number;
  width: number;
  height: number;
  total: number;      // frames in the whole video
  captions: boolean;
  scenes: Scene[];
};
