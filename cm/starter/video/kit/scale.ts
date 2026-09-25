// Sizes in this kit are written for a frame whose short side is 1080 pixels. `useScale`
// turns them into the frame being rendered, so one kit serves every format.
import { useVideoConfig } from "remotion";

export const useScale = () => {
  const { width, height } = useVideoConfig();
  return Math.min(width, height) / 1080;
};
