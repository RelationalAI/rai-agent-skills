# Resolving a Python environment — scoped to this repo only

Shared procedure for finding or creating a Python environment to run tooling this skill
needs (`sqlfluff`, `sqlglot`, `relationalai`/Snowpark, ...). Used by `utils_validation.md`
(layers 1–2) and `utils_auto_execution.md` (Step 0). Each of those
tells you *which package(s)* to ensure are installed and *when* (eagerly up front, or
lazily only once a specific road/step is actually reached) — this file is only the
mechanics of finding/creating the venv and installing into it.

Never run `pip install` (or `python`/`python3` for the command itself) against whatever
happens to be on `PATH`. On a real machine, `pip` and `python3` frequently resolve to
*different, unrelated installs* (Homebrew, Miniconda, pyenv, a project's own `.venv`,
...) — installing with one and running with the other produces a confusing
`ModuleNotFoundError` even though the install reported success. Worse, installing into a
shared/system Python can silently change or break packages other projects depend on.
Treat any dependency-conflict warning from `pip` naming a package or project you don't
recognize as a sign the install landed in the wrong, shared environment — stop and redo
it isolated rather than proceeding.

1. **Already resolved earlier this conversation?** If a prior turn already picked a venv
   for this repo, reuse that same path — skip straight to installing/checking whatever
   package you actually need right now.
2. **Look for a venv already inside *this* repo** (the project you're working in right
   now — not sibling projects elsewhere on the machine):

   ```bash
   find <repo_root> -maxdepth 4 -iname "pyvenv.cfg" -not -path "*/node_modules/*" 2>/dev/null
   ```

   Each hit's parent directory is a venv that belongs to this project. **Do not search
   or reach outside `<repo_root>`** — a venv belonging to a different, unrelated project
   on the machine is out of scope even if it happens to already have the package you
   need installed; that project may pin a different version, run a local/dev checkout
   instead of the published package, or simply not be yours to touch.
3. **If a venv exists in this repo**, check whether it already has the package you need:

   ```bash
   <venv>/bin/python -m pip show <package>
   ```

   - Already there (and at a suitable version, if one is specified) → reuse that
     interpreter as-is, no install needed.
   - Venv exists but lacks it, or `pip` itself is broken/missing in that venv →
     install/repair it there: `<venv>/bin/python -m pip install '<package><version-spec>'`.
     It's this repo's own venv, so adding a dependency it needs is a normal, low-risk
     local change — not a foreign environment.
4. **If no venv exists anywhere in this repo**, create one at the repo root so it
   persists and gets reused on future runs (it will be picked up by step 2 next time):

   ```bash
   python3 -m venv <repo_root>/.venv
   <repo_root>/.venv/bin/python -m pip install '<package><version-spec>'
   ```

   `.venv/` is already covered by this repo's `.gitignore` — confirm that before
   creating it in a different repo that may not have the same rule.

From then on, every command that needs the package(s) you just resolved must run
through that same venv's `bin/python` (or its `bin/<tool>`, e.g. `bin/sqlfluff`), never
a bare `python3`/`pip`/`sqlfluff` that might resolve somewhere else on `PATH`. Remember
the resolved path for the rest of the session so you only do this once per package.

**One venv, added to incrementally.** If a venv already exists in this repo because an
earlier step installed something into it (e.g. `sqlglot` for validation), reuse that
same venv for later needs (e.g. `relationalai` for auto-execution) rather than creating
a second one — step 2 above will find it. Each step only needs to install the specific
package(s) *it* requires; it doesn't need to already have what other steps use.
