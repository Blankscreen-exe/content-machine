// Loads the kit's fonts from its own fonts/ folder and holds the render until they are
// ready, so no frame is drawn in a fallback font and nothing is fetched from the internet.
import { continueRender, delayRender } from "remotion";
import bodyRegular from "./fonts/inter-latin-400-normal.woff2";
import headBold from "./fonts/inter-latin-800-normal.woff2";

const FACES = [
  { family: "Acme Head", url: headBold, weight: "800" },
  { family: "Acme Body", url: bodyRegular, weight: "400" },
];

const handle = delayRender("Loading the kit's fonts");
Promise.all(
  FACES.map(({ family, url, weight }) => new FontFace(family, `url(${url})`, { weight }).load()),
).then((faces) => {
  faces.forEach((face) => document.fonts.add(face));
  continueRender(handle);
});
