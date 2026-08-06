# Repository guidance

## Purpose and interfaces

`icReader` is the lightweight reader for NetCDF conductance products generated
by `icBuilder`. Downstream code, including `icAnalyzer`, depends on its reader
interfaces.

Keep these interfaces distinct:

- `icreader.conductanceimage.ConductanceImage` reads direct conductance-orbit
  products.
- `icreader.splineimage.SplineImage` reads and evaluates spline products and
  exposes coordinate-aware conductance functions.
- `icreader/SplineFactorImage.py` is not exported by `icreader.__init__`; treat
  its support status as unknown until explicitly reviewed.
- `scripts/test_*.py` are manual plotting examples, not an automated test
  suite.

Check Git before trusting the apparent API. The worktree may contain
uncommitted reader changes that are not part of committed HEAD.

## Project memory

Project memory is stored in the repository-root `vault/`.
Before substantive work, read:

1. `vault/01_Project/Current State.md`
2. `vault/05_Handoff/Handoff - Latest.md`
3. `vault/01_Project/Project Brief.md`

Read `vault/02_Algorithm/Reader Interfaces and Data Contract.md` when
changing product compatibility or public reader behavior. Treat older dated
notes at the vault root as historical evidence, not current instructions.

Use this source-of-truth order:

1. live code, Git state, tests, and inspected data products;
2. `Current State.md` and `Handoff - Latest.md`;
3. decision and interface notes;
4. dated historical notes.

If memory conflicts with live evidence, follow the repository and update the
live notes when the task changes project understanding.

## Working rules

- Preserve unrelated and pre-existing worktree changes.
- Keep committed behavior separate from uncommitted experiments.
- Use repository-relative paths in documentation.
- Preserve compatibility with the `icBuilder` product schema and the
  `icAnalyzer` call sites unless a task explicitly coordinates the change.
- Do not modify input NetCDF files merely to test a reader.
- Do not run manual plotting scripts unless overwriting their tracked figures
  or writing to their hard-coded output paths is explicitly intended.
- Avoid editable installation or ordinary imports while tracked
  `__pycache__/` and `icreader.egg-info/` artifacts are dirty; those operations
  can obscure the user's changes.
- Treat tracked example files as fixtures requiring provenance, not as proof
  that every published product remains compatible.

## Scientific coding style

- Write for a small research group. The expected reader is a student or
  scientist who should be able to follow the calculation from top to bottom.
- Use nearby code as the stylistic baseline, not as a ceiling. Do not copy weak
  patterns blindly: identify scientific, numerical, or code choices that could
  be improved, explain the tradeoff, and propose a clearer or safer alternative.
- Adopt improvements when they materially improve correctness,
  reproducibility, clarity, or demonstrated performance. Do not add complexity
  merely because it is conventional in large production systems.
- Let complexity follow the science, numerical method, or actual reuse
  requirements. Prefer direct functions, NumPy arrays, ordinary loops and
  dictionaries, and keep the main calculation visible in execution order.
- Unless current requirements justify them, avoid dataclasses, manager or
  factory classes, generic schemas, version and compatibility frameworks,
  checkpoint/resume machinery, and speculative extension points.
- Retain scientific rigor: make units, coordinates, assumptions, provenance,
  and uncertainty explicit, and add focused tests or reference comparisons for
  consequential calculations.
- Scale packaging, validation, documentation, and abstractions to the code's
  real reuse. A reusable package may justify more structure, but that structure
  should solve a current, explained need.
- If a nominally small feature grows beyond roughly 200 lines or more than two
  new source files, pause and explain why before continuing.

## Verification

No automated test suite or CI workflow was present at the 2026-07-26 review.
A safe syntax-only check that does not import the package or write bytecode is:

```bash
python -c "import ast, pathlib; files=list(pathlib.Path('icreader').glob('*.py'))+list(pathlib.Path('scripts').glob('*.py')); [ast.parse(p.read_text(), filename=str(p)) for p in files]; print(f'parsed {len(files)} files')"
```

For newly staged documentation, use:

```bash
git diff --cached --check
```

The existing worktree may contain unrelated whitespace or generated-file
changes, so inspect targeted diffs rather than assuming a repository-wide
check describes only the current task.

A future functional smoke test should load one tracked conductance file and one
spline file without writing figures or bytecode. Define that check only after
the dependency environment and dirty worktree have been reconciled.

## Automatic memory checkpoints

Project-memory maintenance is a default responsibility. Do not wait for the
user to request a vault update or announce that a session is ending.

Checkpoint after a verified fix or result, a durable interface or data-contract
decision, a changed blocker or next action, and any milestone that would
otherwise leave important understanding only in the conversation.

At a meaningful checkpoint:

1. create `vault/04_Sessions/YYYY-MM-DD.md` only when historical detail
   is worth preserving;
2. rewrite `Current State.md` when verified project state changed;
3. append only durable choices to the decision log;
4. replace obsolete content in `Handoff - Latest.md`;
5. update the interface note only when the supported data contract changed;
6. refresh the handoff's `Portfolio impact` section, using `Central update
   needed: No` when no portfolio-level information changed.

Do not write raw logs, transient speculation, or unchanged state into the
vault. An explicit read-only or no-file-changes request disables automatic
memory writes for that task. Never append new work to an older dated note.
Do not edit the central second brain directly; communicate portfolio changes
through the latest handoff.
