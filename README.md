# Content Machine

A local tool for running a content pipeline: an idea pool, the pieces made from each idea,
and the state of each one on its way to being published. Everything runs on your machine and
nothing is sent anywhere.

It replaces a Notion database, so it has to do three things Notion could not: work offline,
raise its own reminders, and sit next to the files and generation steps that produce the work.

## What it looks like

The screenshots show made-up brands and content; real work never leaves the workspace.

**Dashboard** — what is due now, what is in progress, what to start next, what went out last.

![The dashboard](screenshots/dashboard.png)

**Pieces** — every piece with its stage, paged and sortable, with a search that looks inside
the drafts themselves.

![The pieces list](screenshots/pieces.png)

**A piece** — its drafts in a markdown editor, the files that go with it in a sidebar, and
where it was published underneath.

![One piece, with its drafts and assets](screenshots/piece.png)

**Calendar** — what is due, then the month laid out by due date, coloured by stage.

![The calendar](screenshots/calendar.png)

**Manage** — brands with their voice and profile, each brand's modes, piece types, platforms.

![Managing a brand's modes](screenshots/manage-modes.png)

## Running it

```sh
uv sync --extra dev   # exact versions from uv.lock, into .venv

cm init           # create the workspace: session rules, skills, video starter files
cm video setup    # only for video: install the toolchain (downloads, once)
cm render 12      # render video piece 12 into its assets; --draft for a quick half-size one
cm serve          # this machine only
cm serve --lan    # also reachable from a phone on the same network
cm where          # show the workspace paths
```

To have `cm` in every terminal, not only with the `.venv` active, register it:

```sh
./install.sh                  # Linux, macOS, Git Bash
.\install.ps1                 # Windows PowerShell
```

Both wrap `uv tool install --editable` and `uv tool update-shell`: `cm` gets its own
environment in uv's tool folder, and that folder goes on PATH. The install is editable, so it
runs the code in this repo (a `git pull` needs no reinstall) and the default workspace stays
`<repo>/workspace`. Options: `--uninstall` / `-Uninstall` removes it, `--no-path` / `-NoPath`
leaves PATH alone, `--native-tls` / `-NativeTls` uses the system's certificates on networks
that inspect HTTPS. If PowerShell blocks scripts: `powershell -ExecutionPolicy Bypass -File .\install.ps1`.

`cm init` copies the session rules and skills from `cm/starter/` into the workspace. Brands
are added under Manage in the app; a new brand's voice and profile start from the
placeholder templates in `cm/starter/brand/`. Real brands only ever live in the workspace
database, never in this repository.

The address printed on start carries a one-time token; the app refuses requests without it.

## How it is put together

| Concern | Choice | Why |
|---|---|---|
| HTTP | FastAPI + Uvicorn | Form validation, dependencies and streaming come with it; streaming matters for the generation step that comes next |
| Database | SQLite via SQLModel | One file, no server. SQLModel gives typed models over SQLAlchemy |
| Schema changes | Alembic | The database will hold real work, so changes have to migrate rather than be recreated |
| Pages | Jinja2 templates + htmx | Server-rendered fragments, no build step, no frontend framework for what is a CRUD screen |
| CLI | Typer | Same operations as the UI, without a browser |
| Editor | Toast UI Editor | Markdown and WYSIWYG in one component, with a toggle, and no build step |
| Paged lists | DataTables 3 | Paging, rows per page and column sorting on the lists, with no dependencies of its own; it keeps its place when htmx redraws a list |
| Video | Remotion (Node) | Frames written as React components, rendered frame by frame; see [Videos](#videos) |
| Tests | pytest + FastAPI TestClient | Covers the routes, the audit trail, file safety and the migrations |

htmx, the editor and DataTables are vendored in `cm/static/vendor/` so the app loads nothing from the
internet. Use the editor's `-all` build: the plain one expects ProseMirror to be supplied
separately.

## Writing

Each piece has a folder, and its drafts are plain markdown files in it. The browser and a
terminal session read and write the same files, so there is no import or export.

- The editor is a textarea with Toast UI mounted on top. The textarea stays in the form, so
  saving works the same way if the editor fails to load.
- A save carries a fingerprint of the file it was given. If a session wrote to that file in
  the meantime, the save is refused and offers to reload or to overwrite deliberately.
- Pasted images are stored in the piece's `assets/` folder. The markdown keeps a relative
  path so the folder stays self-contained; the app serves the image for display.
- File routes only resolve names inside the piece's own folder.
- Unsaved typing is marked next to Save, Ctrl+S saves, and leaving the page or switching to
  another file asks first.
- A piece type can carry a character limit (LinkedIn's 3,000, X's 280). The count under the
  editor is of the text as "Copy as plain text" produces it, which is what the platform gets.
- Copying falls back to the older select-and-copy command where the clipboard API is not
  available, as on plain http from another device on the local network.

## Assets

A piece's images, PDFs (a LinkedIn carousel is posted as one), Photoshop files, video and
audio live in its `assets/` folder. They are uploaded through the browser, so they reach the
folder from any device: drop several files on the Assets panel, and download or delete them
from there. Video and audio play in the panel.

- Only these types are stored or served; limits are 10 MB for images, 50 MB for PDFs,
  200 MB for Photoshop files, 500 MB for video (MP4, WebM) and 50 MB for audio (MP3, M4A;
  WAV 200 MB). An HTML or SVG file is never served from the app's address.
- Each type is served with a content type the app states itself, not one read from the
  system, and video answers range requests so it can be scrubbed.
- Each upload is written under a temporary name and renamed once complete, so a failed or
  oversized upload leaves nothing behind.
- Deleting moves the file to `trash/<brand>/<piece folder>/assets/`.
- "Open folder" opens it in the file manager, and only appears on the machine running the app.

## Dashboard

The page the app opens on: what is due today or overdue, what is in progress, the pool ideas
to start next, and what went out last, each linking through. It follows the brand filter.

## Repurposing

"Make a … from this" on a piece's page makes a piece of another type with the same idea and
title, and remembers which piece it came from. Its brief names the source draft and asks the
session to use the `derive` skill; on the machine running the app a session opens straight
away.

## Videos

A video piece is written as `frames.md`: what is said and shown, frame by frame. A new one
opens on a template.

```md
Format: vertical          # or square, portrait, landscape
Captions: on

## Hook (4s)
Script: What is said while this frame is on screen.
On screen: The words and pictures shown.
Animation: How they move.
```

A length like `(4s)` fixes how long a frame runs; without one it runs as long as its script
takes to say. The file is read strictly: under the editor it shows what it will make ("5
frames · vertical 1080×1920 · captions on") or lists every problem with its frame and line.
It is always saved as written, so nothing typed is lost to a mistake.

### Building

**Build video**, in a video piece's Video panel, opens a session on this machine with the
`video` skill. It reads `brief.md`, whose Video section gives the frames as the render will
read them (or what must be fixed first), where each sits on the timeline, and the imports
for the brand's kit and images, ready to paste. The skill writes `video/Video.tsx` with the
kit only: what the kit lacks is added to the kit, so every video keeps the brand's look.
It renders a draft, looks at stills from it, and leaves the final render until the voice
is on. A brand without a kit is asked about first; its kit starts from the example.

Who does what changes with it: in the workspace's `CLAUDE.md`, videos and the brand's kit
are the session's work, while images, diagrams and the voice stay yours. An existing
workspace keeps its own `CLAUDE.md` (`cm init` never overwrites it), so copy that change
across by hand, or run `cm init --force` if you have not edited the starter files.

### Voice

**Record voice**, in the Video panel, opens the piece's Voice page: the draft, with a
teleprompter under it that shows the line to read and lights each word as it is due, and
the next line after it. Recording counts down, then plays the draft with its sound off
while you read; the whole video is one take, so a sentence can carry across a frame change.
A browser only allows the microphone on a secure address, which over plain http means
`localhost`: open the page there, on the machine running the app, to record. Anywhere else,
including the `--lan` address on the same machine, the page still plays but cannot record.

Takes are kept in the piece's `voice/` folder as `take-1.webm`, `take-2.webm` and on. A take
is never cut: which one is used, its offset against the video, where it is trimmed, its
volume, and the music from the brand's library with its volume are numbers in
`voice/mix.json`, so any choice can be undone. "Play with voice" plays the draft with the
take and music lined up as a render will mix them, from the settings as they stand, saved
or not. A `mix.json` that cannot be read is reported, never replaced.

A render plays the voice and music itself, under the piece's video, so no video or kit has
to handle sound. The music loops if it is short and fades out over the last second. The
files are copied beside the render, so it sees them and nothing else of the workspace.

### Rendering

A piece's video is drawn by `video/Video.tsx` in its folder, which exports a component
named `Video`. It draws every frame with the brand's kit, from props the app hands it:
each frame's script, what is on screen, how it moves, and where it sits on the timeline.
Their shape is `VideoProps`, which the app writes to `video/props.ts` in the workspace.
The app registers the component itself, with the size, frame rate and length it worked
out, so a video only has to draw.

Timing comes from `frames.md`: a frame with a length runs exactly that long; otherwise it
runs as long as its script takes to say at about 150 words a minute, plus a breath. The
voice is recorded to this pace afterwards.

The Render panel on a video piece's page, or `cm render <id>`, renders the saved frames at
full size into the piece's assets as `video.mp4`, keeping earlier ones as `video-2.mp4` and
on. A draft (`--draft`) renders at half size, quickly, replacing `draft.mp4`. Rendering
never changes the piece's stage.

From the page, the render runs in the background and the panel shows how far it has got;
when it is done the video appears in the Assets panel. Any device can start one, since it
renders on the machine running the app, and a piece renders once at a time from the page.
Each render works in a folder of its own under `.cm/renders/`, so a render from the page and
one from the terminal never collide. The folder is removed once the video is in place; if
the render fails, it is kept and the error says what Remotion said, without its stack
trace, and names the cause where Remotion does not.

### The video toolchain

Videos are drawn with [Remotion](https://www.remotion.dev): each frame is a React component
rendered in a headless Chrome. It needs Node 18 or later, and only video needs it; the rest
of the app never touches Node. `cm video setup` installs it into the workspace, and is the
only step that downloads anything for video:

- `npm ci` installs exactly the packages in `package-lock.json` and refuses any whose contents
  do not match the checksum recorded there. Every locked version was at least two weeks old
  when the lockfile was made (`npm install --before=<date>`), so a release that is hijacked
  and pulled within days never gets in.
- No package runs code while it installs (`--ignore-scripts`, also set in the workspace's
  `.npmrc`). Only esbuild has an install script, and it only double-checks a binary its
  platform package already provides.
- `npm audit signatures` checks every package was signed by the npm registry.
- Remotion then fetches its headless Chrome, about 110 MB, from Google's Chrome for Testing
  downloads. After that, rendering works offline.

The packages: `remotion` and `@remotion/cli` render; `react` and `react-dom` are what the
frames are written in; `roughjs` draws the hand-drawn boxes and arrows. They sit at the
workspace root, so every piece folder beneath it finds them.

Remotion is free for individuals and companies of up to three people; larger companies need
a [company licence](https://www.remotion.dev/license). It reports usage to remotion.pro only
when a licence key is set, and this app never sets one.

### Brand resources

What a brand reuses across its pieces lives in `resources/<brand>/` in the workspace:
`images/` (a portrait, logos), `music/` (what a video can play under the voice) and `kit/`,
the brand's video kit. A kit is the code that gives the brand's videos their look — colours,
fonts, background, boxes, arrows, captions — and a video imports only from it, so the look
stays the same from one video to the next. `cm init` puts an example kit for a made-up brand
in `video/example-kit/` to start from. Kits load their fonts from files in their own folder,
never from the internet, and size everything to the frame, so one kit serves every format.

Images and music are uploaded on the brand's Manage page, where each file goes to the folder
its type belongs to, by the same rules as a piece's assets.

## Layout

```
cm/
  app.py          application factory
  cli.py          the `cm` command
  routes/         page routes, one module per screen; htmx swaps the fragments
    manage/       the Manage tab, one module per section
  crud.py         database operations, shared by the web app and the CLI
  choices.py      the rules the managed lists share: unique names, turn off, delete if unused
  models.py       tables: brands, modes, piece types, platforms, ideas, pieces, publications
  scaffold.py     starter files for `cm init`, and the text new brands and modes begin with
  database.py     engine, sessions, foreign keys, migrate-on-start
  schedule.py     what is overdue or due soon
  month.py        a month laid out in weeks, with the pieces due on each day
  search.py       full-text search over the drafts (SQLite FTS5), kept in step with the files
  workspace.py    a piece's folder: where it is, its brief, moving it to the trash
  files.py        reading and saving drafts inside a piece folder
  assets.py       a piece's images, PDFs, Photoshop files, video and audio: what is stored, and how
  frames.py       reading a video's frames file, and every problem in it
  formats.py      the shapes a video renders in: vertical, square, portrait, landscape
  toolchain.py    installing and checking the video toolchain: Node, npm packages, the browser
  timing.py       how long each frame runs, and the props a video is handed
  video.py        running Remotion: the only module that knows how a video is rendered
  renders.py      a video piece rendered into its assets: drafts replaced, finals kept
  render_jobs.py  renders started from the page, run in the background and followed
  video_brief.py  the Video section of a video piece's brief
  voice.py        a video's takes, and the mix: which take, lined up and trimmed, and the music
  remotion/       the TypeScript side of that: the props a video gets, the entry that registers it
  resources.py    what a brand reuses across pieces: images, music, its video kit
  terminals.py    opening a terminal session in a piece folder
  desktop.py      opening a folder in the system's file manager
  dates.py        stored UTC times to local calendar dates
  security.py     access token
  settings.py     configuration and workspace location
  templating.py   template setup and the context every page shares
  starter/        what `cm init` copies into a workspace, and what new brands and pieces start from
    video/        the pinned npm packages, and the example brand kit
  templates/      base page and htmx partials
  static/         base.css (layout), themes/ (appearance), vendor/
alembic/          migrations
tests/
workspace/        your content and the database (not in git)
```

## Themes

`static/base.css` holds structure and the responsive rules; a theme file holds only colours,
fonts and borders. Drop a stylesheet into `static/themes/` and it appears in the theme picker;
the choice is stored in the database, so it follows you to whatever device you open it on.

The same page in the three themes that ship with it — modern, 1996 and scholar:

| Modern | 1996 | Scholar |
|---|---|---|
| ![Modern](screenshots/theme-modern.png) | ![1996](screenshots/theme-1996.png) | ![Scholar](screenshots/theme-scholar.png) |

## Data model

An **idea** is the unit of thinking. A **piece** is one thing that gets published — a blog post,
a LinkedIn post, a carousel — and an idea can produce several, each with its own type, stage and
due date. An idea can also stand alone as a single piece.

Stages: not started → draft → wip → ready → published.

**Piece types**, **platforms** and each brand's **modes** are lists you manage under the Manage
tab, not values in the code. Records point at them by id, so renaming one renames it everywhere.
Turning one off hides it from new choices while the records that use it keep it; one that is in
use cannot be deleted. Idea statuses, piece stages and priorities stay in code, because the app's
own behaviour depends on them.

A piece type can be marked **video**: its pieces are frames rendered into a video rather than
text pasted onto a platform, so it has no character limit. The "youtube short" type starts out
as one, opening on `frames.md`.

A brand's **voice** and **profile** are stored on the brand and edited on its Manage page. A
mode has a description. All three are copied into `brief.md` when a session starts, so the
database is their only home and a session still reads everything from one file.

Every status and stage change is written to the **events** table, so the history of a piece is a
record rather than a single current value: when it was drafted, when it became ready, when it went
out. Making a piece from an idea promotes that idea out of the pool, because it is now in motion.

The pieces list sorts by due date with undated work last, and marks anything overdue that has not
been published.

## Calendar and reminders

The Calendar tab lays a month out in weeks, starting on Monday, with each piece on its due day in
its stage's colour; published work stays on it. Months are plain addresses (`/calendar?month=2026-09`),
so they can be bookmarked. On a phone the grid becomes a list of the days that have something on them.

Unpublished pieces that are overdue, or due within a window set in Settings (a week by default),
are listed above the month on the Calendar tab and counted on that tab. There is no background process: the
reminder is wherever you already look.

## Searching drafts

"Search drafts" on the Pieces tab finds pieces by the words in their draft files, with word forms
("queue" finds "queues") and the last word allowed to be unfinished. A result opens the piece on
the file that matched.

Terminal sessions edit drafts directly, so the index catches up before every search, reading only
files whose size or modification time changed. It lives in `.cm/search.db` in the workspace, apart
from `content.db`: it holds nothing of its own, so deleting it only means the next search rebuilds it.

## Publishing

Recording a publish on a piece's page (platform, link, date) moves the piece to published. The
platform comes from the managed list, so the same one is always spelled the same way.
`cm published <id> --platform <name>` does the same from a terminal session.

## Deleting

Deleting a piece moves its folder to `trash/<brand>/` in the workspace, so deleting the entry never
deletes the work. If the folder cannot be moved — on Windows, while a terminal is open in it —
nothing is deleted and the page says why.

## Licence

MIT. See `LICENSE`. The example kit's font, Inter, is under the SIL Open Font License, in
`cm/starter/video/kit/fonts/OFL.txt`.
