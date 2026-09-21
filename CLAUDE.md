## Built to last

This is not throwaway work. Someone — probably me — will be maintaining it in ten years.

- **Modular.** One module, one job. A new feature should mean a new file more often than a
  bigger file. If two things change for different reasons, they don't belong together.
- **Replaceable parts.** Anything we might swap later (the editor, the theme, the terminal,
  the storage) sits behind a clear seam, so swapping it touches one place.
- **Obvious over clever.** The version a tired person can read at midnight wins.
- **No temporary hacks.** If it is worth doing twice, do it properly the first time.

## What goes in the repo

Only the system and dummy starter material. No real brand's name, voice, handles, colours,
logos, drafts or images ever goes in — not in code, templates, tests or commit messages. Real
brands live in the workspace, which is never committed. Examples use made-up names like
"Acme Co" and "Example Person".

## Standards

Every decision in this codebase has to be one we can defend out loud.

- **Justify or don't do it.** No clever tricks without a reason, no dependency we can't explain, no
  pattern copied because it looked impressive. If the simple version is good enough, ship the simple
  version.
- **Ask when unclear.** A wrong guess baked into the code is worse than a question. Ask.
- **Leave no mess.** No dead code, no commented-out experiments, no half-finished features sitting in
  the tree. If something is exploratory, it goes in a scratch folder or gets deleted.
- **Write for a reader.** Clear names, short focused modules, and comments that say *why* rather than
  restating *what*. Every module opens with a line explaining what it is for.
- **Standard library first.** Reach for a dependency only when it earns its place, and say why in the
  code or the README.
- **Tests where they pay.** Cover the logic that would quietly corrupt data or lose work. Don't write
  ceremonial tests for getters.
- **Errors are honest.** Fail loudly with a message that says what to do next, rather than swallowing
  the problem.
