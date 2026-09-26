---
name: video
description: Build a video piece's video/Video.tsx from its frames.md, drawn with the brand's kit.
---

# Build a video

Use once I have finalised a video piece's `frames.md`, and again whenever it changes.

## Before writing anything

1. Read `brief.md`, especially its Video section and the Brand profile.
2. If the Video section lists problems with `frames.md`, stop and tell me. Do not fix my
   frames unless I ask.
3. If the brand has no kit yet, stop and ask. With my go-ahead, copy the example kit named
   in the brief into the brand's kit folder, then restyle it from the Brand profile and any
   reference images I give you: colours, fonts, shapes. Fonts go in the kit's `fonts/`
   folder as files, never fetched from the internet.

## Writing `video/Video.tsx`

- Export `Video`, a component taking `VideoProps` (the import is in the brief). The app
  registers it with the right size, frame rate and length; do not register anything.
- Draw with the kit only. Import everything visual from the kit's index. If a frame needs
  something the kit lacks, add it to the kit as a component in the kit's style, and tell me
  what you added. No colours, fonts or one-off styling in `Video.tsx`: the kit is what
  keeps every video looking like the brand.
- One `<Sequence from={scene.from} durationInFrames={scene.duration}>` per scene, in order.
  Never write a timing down: time each animation from its scene's start, and anything tied
  to what is said from `scene.speech`. The timings change when `frames.md` does.
- If `captions` is true, place the kit's `Captions` once, over the whole video, not inside
  a scene: `<Captions scenes={scenes} />`. Once there is a take the app times each word to
  the voice, and captions follow the voice rather than the cuts between scenes.
  `scene.words` gives the moment each word is said, for anything else that should move
  with the voice.
- Follow each frame's "On screen" and "Animation". Where they are loose, choose something
  in the kit's style and tell me what you chose.
- Lay out in kit units, as the kit does, so the video works in the format in the brief.
- Keep every frame the same each time it renders: no `Math.random()`, no dates, a fixed
  `seed` on every rough.js shape.
- Brand images (a portrait, a logo) are imported by path, as the brief shows. Never
  invent an image; if a frame needs one I have not given, leave the space and tell me.

## Checking it

1. Render a draft: `cm render <piece id> --draft`. If it fails, the error says why; fix it
   and render again.
2. Look at it. From the workspace root, pull a still from the middle of each scene
   (seconds = frame / 30):
   `npm exec --no -- remotion ffmpeg -y -ss <seconds> -i <piece folder>/assets/draft.mp4 -frames:v 1 <piece folder>/still.png`
   Read each still, fix what is off, and delete the stills when you are done.
3. Tell me what you built and anything you chose or added. Do not render a final: that
   waits until my voice is on it.
4. `cm note <piece id> "Built the video from frames.md"`.
