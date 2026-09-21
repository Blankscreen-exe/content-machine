# Content Machine

A local tool for running a content pipeline: an idea pool, the pieces made from each idea,
and the state of each one on its way to being published. Everything runs on your machine and
nothing is sent anywhere.

It replaces a Notion database, so it has to do three things Notion could not: work offline,
raise its own reminders, and sit next to the files and generation steps that produce the work.

## Running it

```sh
uv venv
uv pip install -e ".[dev]"

cm init           # create the workspace: rules, skills and a starter brand
cm serve          # this machine only
cm serve --lan    # also reachable from a phone on the same network
cm where          # show the workspace paths
```

`cm init` copies `cm/starter/` into the workspace. The one brand in it, `example`, is a
placeholder for a made-up company: copy its folder to `brands/<your-slug>/` and fill it in.
Real brands only ever live in the workspace, never in this repository.

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
| Tests | pytest + FastAPI TestClient | Covers the routes, the audit trail, file safety and the migrations |

htmx and the editor are vendored in `cm/static/vendor/` so the app loads nothing from the
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

## Layout

```
cm/
  app.py          application factory
  routes.py       page routes; htmx swaps the fragments
  crud.py         database operations, shared by the web app and the CLI
  models.py       tables: brands, ideas, pieces, publications, events, settings
  database.py     engine, sessions, migrate-on-start
  security.py     access token
  settings.py     configuration and workspace location
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

## Data model

An **idea** is the unit of thinking. A **piece** is one thing that gets published — a blog post,
a LinkedIn post, a carousel — and an idea can produce several, each with its own type, stage and
due date. An idea can also stand alone as a single piece.

Stages: not started → draft → wip → ready → published.

Every status and stage change is written to the **events** table, so the history of a piece is a
record rather than a single current value: when it was drafted, when it became ready, when it went
out. Making a piece from an idea promotes that idea out of the pool, because it is now in motion.

The pieces list sorts by due date with undated work last, and marks anything overdue that has not
been published.
