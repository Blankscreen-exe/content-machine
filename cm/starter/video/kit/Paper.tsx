// The background every video sits on: warm paper with a faint dot grid.
import React from "react";
import { AbsoluteFill } from "remotion";
import { useScale } from "./scale";
import { color } from "./tokens";

export const Paper: React.FC = () => {
  const cell = 54 * useScale();
  return (
    <AbsoluteFill style={{ backgroundColor: color.paper }}>
      <AbsoluteFill
        style={{
          backgroundImage: `radial-gradient(${color.grid} ${cell / 12}px, transparent ${cell / 12}px)`,
          backgroundSize: `${cell}px ${cell}px`,
        }}
      />
    </AbsoluteFill>
  );
};
