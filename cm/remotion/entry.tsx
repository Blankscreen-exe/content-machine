// Written by Content Machine for one render; do not edit.
//
// Registers the piece's video with the size, frame rate and length the app worked out,
// and plays the voice and music under it, so a piece only has to draw its frames and
// every video mixes its sound the same way. __VIDEO__ and __PROPS__ are filled in with
// paths relative to this file.
import React from "react";
import { AbsoluteFill, Composition, Html5Audio, Sequence, interpolate, registerRoot, staticFile } from "remotion";
import type { VideoProps } from "__PROPS__";
import { Video } from "__VIDEO__";

// The music fades out over the last second, rather than stopping mid-note.
const FADE_SECONDS = 1;

const Soundtrack: React.FC<VideoProps> = ({ voice, music, total, fps }) => (
  <>
    {voice ? (
      <Sequence from={voice.from} layout="none">
        <Html5Audio
          src={staticFile(voice.src)}
          trimBefore={voice.trimBefore}
          trimAfter={voice.trimAfter ?? undefined}
          volume={voice.volume}
        />
      </Sequence>
    ) : null}
    {music ? (
      <Html5Audio
        src={staticFile(music.src)}
        loop
        volume={(frame) => interpolate(frame, [total - FADE_SECONDS * fps, total], [music.volume, 0],
                                       { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
      />
    ) : null}
  </>
);

const Whole: React.FC<VideoProps> = (props) => (
  <AbsoluteFill>
    <Video {...props} />
    <Soundtrack {...props} />
  </AbsoluteFill>
);

registerRoot(() => (
  <Composition
    id="Video"
    component={Whole}
    calculateMetadata={({ props }: { props: VideoProps }) => ({
      durationInFrames: props.total,
      fps: props.fps,
      width: props.width,
      height: props.height,
    })}
  />
));
