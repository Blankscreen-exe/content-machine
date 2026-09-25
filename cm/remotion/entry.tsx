// Written by Content Machine for one render; do not edit.
//
// Registers the piece's video with the size, frame rate and length the app worked out,
// so a piece only has to draw its frames. __VIDEO__ and __PROPS__ are filled in with
// paths relative to this file.
import React from "react";
import { Composition, registerRoot } from "remotion";
import type { VideoProps } from "__PROPS__";
import { Video } from "__VIDEO__";

registerRoot(() => (
  <Composition
    id="Video"
    component={Video as React.FC<VideoProps>}
    calculateMetadata={({ props }: { props: VideoProps }) => ({
      durationInFrames: props.total,
      fps: props.fps,
      width: props.width,
      height: props.height,
    })}
  />
));
