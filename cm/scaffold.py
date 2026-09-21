"""Starter files for a new workspace.

A terminal session opened in a piece folder picks up `CLAUDE.md` for the standing rules
and the skills for the jobs that repeat. These are written once and then belong to you —
`cm init` never overwrites a file that already exists.
"""
from __future__ import annotations

from pathlib import Path

from .settings import get_settings

CLAUDE_MD = """# Working on content in this workspace

This folder holds content, not code. Each piece of content has its own folder under
`content/<brand>/<date>-<slug>/` containing `brief.md` (generated), the drafts, and an
`assets/` folder for images.

## Who does what

**You (Claude) do the content:** ideas, talking points, outlines, drafts, edit passes,
turning one piece into another, design specs, and prompts for image generation.

**I do the rest:** the voice pass on every draft, all visual work in Photoshop, labels,
memes, and publishing. You never do those.

## Rules

- **Never publish anything, anywhere.** The last step is always mine.
- **Never invent my experiences.** If a piece needs a client story, leave
  `[MY STORY: what goes here]` and move on.
- **Never state a fact without a source.** Mark anything unverified clearly.
- **Drafts are clay.** Write them so I can rewrite them. Don't defend your phrasing.
- **Match the brand voice** in `brands/<brand>/voice.md`. If there is no voice file for a
  brand, ask me before drafting.

## Files in a piece folder

| File | What it is |
|---|---|
| `brief.md` | Generated before each session. Never edit it; it is overwritten. |
| `blog.md`, `linkedin.md`, `x.md` | Drafts, named after the channel |
| `spec.md` | Design pack: layout in ASCII, labels, and the copy deck |
| `props.md` | Prompts for images I will generate elsewhere |
| `assets/` | Images pasted into a draft |

## Reporting back

The web app tracks stages. When something changes, say so:

```
cm stage <piece id> draft      # not started | draft | wip | ready | published
cm note <piece id> "what you did"
```

The piece id is in `brief.md`.
"""

SKILLS: dict[str, tuple[str, str]] = {
    "outline": (
        "Plan the structure of a blog post before drafting it.",
        """# Outline a piece

Use when a piece needs structure before anyone writes prose.

## Steps

1. Read `brief.md` and the brand's `voice.md`.
2. Ask what the reader should believe or do by the end. One sentence. If the brief does
   not answer it, ask me.
3. Propose three hooks. Do not pick one for me.
4. Lay out the sections: what each one claims, and what evidence or story it needs.
5. Mark every place that needs something only I can supply: a client story, an opinion,
   a meme, a number.
6. Mark every factual claim that will need a source.
7. Write the result to `outline.md` in the piece folder. Do not start drafting.
""",
    ),
    "derive": (
        "Turn a finished blog post into posts for the other channels.",
        """# Derive the other pieces

Use once a blog draft exists and I have done the voice pass on it.

## Steps

1. Read the blog draft in this folder, plus `voice.md`.
2. Produce, as separate files:
   - `linkedin.md` — the post, with the hook in the first two lines, short paragraphs,
     no markdown headings (LinkedIn strips them), 3-5 hashtags at the end.
   - `x.md` — a thread; each tweet under 280 characters, numbered.
   - `quotes.md` — 5 to 8 lines from the blog that stand on their own.
3. Keep my phrasing wherever it already works. This is repackaging, not rewriting.
4. Leave `[MY STORY: ...]` markers in place; never fill them in.
5. Tell me which claims in the derived pieces still need a source.
""",
    ),
    "spec": (
        "Write the design pack for a visual piece: layout, copy deck and image prompts.",
        """# Design pack

Use for a carousel, an infographic, or any piece I will build in Photoshop.

## Steps

1. Read `brief.md`, the draft, and the brand's `voice.md`.
2. Write `spec.md` with:
   - Canvas sizes and export format.
   - A few brand constants: colours, fonts, margins.
   - A page map: what each page contains.
   - **ASCII layouts** with placeholders, never the real text:
     `[HEADLINE - white]`, `[PROP IMAGE GOES HERE]`, `[TICK ROW 1]`.
   - A **copy deck** at the end: the real text, per page, in code blocks, with markers
     for what goes bold or in the accent colour.
3. Write `props.md` with four complete, standalone prompts per image, each ending with
   the same style rules so the set matches. Leave a **Chosen:** line under each for me to
   fill in.
4. Do not place labels, choose memes, or design anything. Leave the space and say what
   belongs there.
""",
    ),
}


def init_workspace(force: bool = False) -> list[Path]:
    """Create the workspace folders and starter files. Returns what was written."""
    settings = get_settings()
    written: list[Path] = []

    for folder in (settings.brands_dir, settings.content_dir):
        folder.mkdir(parents=True, exist_ok=True)

    claude_md = settings.workspace / "CLAUDE.md"
    if force or not claude_md.exists():
        claude_md.write_text(CLAUDE_MD, encoding="utf-8")
        written.append(claude_md)

    for name, (description, body) in SKILLS.items():
        skill = settings.workspace / ".claude" / "skills" / name / "SKILL.md"
        if not force and skill.exists():
            continue
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}",
                         encoding="utf-8")
        written.append(skill)

    return written
