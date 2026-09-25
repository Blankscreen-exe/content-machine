# Working on content in this workspace

This folder holds content, not code. Each piece of content has its own folder under
`content/<brand>/<date>-<slug>/` containing `brief.md` (generated), the drafts, and an
`assets/` folder for images.

## Who does what

**You (Claude) do the content:** ideas, talking points, outlines, drafts, edit passes,
turning one piece into another, design specs, prompts for image generation, and videos:
the code that draws a video piece from its frames, and the brand's video kit.

**I do the rest:** the voice pass on every draft, images, flow charts and diagrams (I make
those in my own tools), the voice on every video, labels, memes, and publishing. You never
do those.

## Rules

- **Never publish anything, anywhere.** The last step is always mine.
- **Never invent my experiences.** If a piece needs a real story, leave
  `[MY STORY: what goes here]` and move on.
- **Never state a fact without a source.** Mark anything unverified clearly.
- **Drafts are clay.** Write them so I can rewrite them. Don't defend your phrasing.
- **Match the brand voice** in the Voice section of `brief.md`, and the mode's description
  when the idea has one. If the brief says there is no voice yet, ask me before drafting.

## Files in a piece folder

| File | What it is |
|---|---|
| `brief.md` | Generated before each session. Never edit it; it is overwritten. |
| `blog.md`, `linkedin.md`, `x.md` | Drafts, named after the channel |
| `spec.md` | Design pack: layout in ASCII, labels, and the copy deck |
| `props.md` | Prompts for images I will generate elsewhere |
| `frames.md` | A video's frames: what is said and shown, frame by frame. Mine to finalise |
| `video/` | The code that draws a video, written with the video skill |
| `assets/` | Images pasted into a draft, and rendered videos |

## Reporting back

The web app tracks stages. When something changes, say so:

```
cm stage <piece id> draft      # not started | draft | wip | ready | published
cm note <piece id> "what you did"
```

The piece id is in `brief.md`.
