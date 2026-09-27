# Project context for Claude Code

This file is read automatically by Claude Code. It exists so a fresh session
has full context on this project without the user re-explaining it. The
notebook is the source of truth for code; this file records what the code is
for, why it looks the way it does, and what is still open.

## What this project is

An organic chemistry study tool that helps students master stereochemistry
(R/S, and eventually E/Z) by parsing a photo or drawing of a molecule into a
validated digital representation, grading correctness with deterministic
chemistry rules, and using an LLM only to explain results in plain language.

**The core design principle, non-negotiable:** an LLM never computes
chemistry. RDKit (deterministic, rule-based) always decides what's correct.
The LLM only explains a result that's already been computed. Do not suggest
architectures that let an LLM guess or compute a chemistry answer directly.

**Core scope:** review one static structure, grade the student's R/S answer,
and pinpoint *why* it is right or wrong (README: "pinpoints exactly what's
wrong"). Reaction-mechanism grading (README Milestone 4) is a separate, later,
optional feature and not part of this loop -- don't pull it into current work.

## Current phase

**Phase 1: research & validation**, built in a single Jupyter notebook, not a
production codebase yet. Code quality bar right now is "correct and
well-tested," not "production-structured." Do not push migration to a
multi-file package (Phase 2) until Phase 1 is proven. See `README.md` for the
milestone list (its checkboxes lag behind reality -- Milestone 3 is effectively
done and Milestone 5 is far along).

## Layout and environment

- Notebook: `notebooks/Untitled-1.ipynb`. Test images (`aspirin_test.png`,
  `temp_molecule.png`) and `requirements.txt` sit beside it in `notebooks/`.
  Relative image paths resolve from the kernel's working directory -- if a
  path breaks, check `os.getcwd()` first.
- The notebook is too large for the Read tool. Inspect it with the venv
  Python's `json` module (cells have stable ids), not Read.
- The user edits the notebook live in VS Code. Changes written to the .ipynb
  on disk are not reliably picked up by the open editor/kernel -- after any
  disk edit, the user must revert the file and re-run the affected cells.
  Stale kernel state has caused several false "still broken" reports.
- venv: `.venv-decimer` at the repo root, Python 3.12.6 (kernel
  `.venv-decimer`). Key pins: rdkit 2026.3.4, decimer 2.8.0, tensorflow 2.20.0.
- `requirements.txt` is UTF-16 with a BOM (from PowerShell `pip freeze >`).
  VS Code shows it fine and pip should read it; re-save as UTF-8 before any
  Docker/CI use in Phase 2.
- Local LLM: Ollama, `qwen3:1.7b`, at `http://localhost:11434/api/generate`.
  Dev machine is CPU-only (ThinkPad L13, Core i5), so generation is slow.
  Qwen3 is a hybrid "thinking" model: thinking is left ON (default).
  `"think": False` was tried and made results worse (one response omitted the
  correct label entirely). Timeout is 100s in `qwen_JSONresponse`.
- Production LLM plan (not built): a hosted open-source model API (e.g. Groq),
  because on-device inference was judged too slow. A bigger model on this
  CPU-only laptop would make timeouts worse, not better.

## Architecture (5 layers)

1. **Input capture** -- photo upload or in-app editor (not built).
2. **Vision parsing (OCSR)** -- DECIMER, image to SMILES. Built, benchmarked.
3. **Chemistry validation (RDKit)** -- deterministic ground truth. Built.
4. **Grading** -- student answer vs RDKit's answer. Built.
5. **LLM tutoring layer** -- explains a graded result. Built, being hardened.

## Key functions (see notebook cells for code)

- `validate_molecule(smiles | list)` (cell `693fc9de`) -- returns one dict per
  input, always with keys `Valid`, `Number of stereocenters`, `Stereocenters`,
  `Undefined stereocenters` (never drop a key from any return path). Each
  stereocenter has `Atom index`, `label` (R/S) and `Priorities` (CIP-ranked
  neighbors: `priority_rank`, `atom_symbol`, `attached_to`). It
  canonicalizes before indexing (fixes atom-order-dependent indices) and calls
  `AddHs` so the four real substituents, including H, are visible. The
  early definition in cell `038db903` is the old version; run order decides
  which one is live.
- `grade_stereocenter_answer(smiles, atom_index, answer)` -- returns
  `{correct_label, student_answer, is_correct}` or `{"error": ...}`. It says
  right/wrong only; it does not explain why.
- `get_substituent_priorities`, `build_priority_reason`, `describe_rotation`
  (cell `reason_rebuild1`) -- the deterministic "why" facts. Priorities come from
  RDKit's `_CIPNeighborOrder`. The reason is an atomic-number comparison of the
  top two groups. `describe_rotation` is a lookup: R -> clockwise, S ->
  counterclockwise (R/S is defined as that rotation with the lowest-priority
  group pointing away, so no GetChiralTag() work is needed).
- `build_explanation_prompt(grading, smiles, priorities, rotation)` -- assembles
  those facts into the prompt and tells the model to restate them, not compute.
- `qwen_JSONresponse(prompt)` -- Ollama call; returns text, truncated flag,
  duration.
- `check_explanation(grading, response, priorities, rotation)` -- verifies the
  LLM output before it is trusted.
- `get_safe_explanation(grading, smiles, atom_index)` -- the entry point. Builds
  a plain `fallback_text` first, then tries the LLM and returns the LLM text
  only if every check passes; otherwise (or on timeout/network error, or a
  grading error) it returns the fallback. It never crashes on a slow Ollama.
  Note the fallback carries no "why", so a rejected response loses the
  pinpointing that is the point of the layer.

## Design decisions to preserve

- **Check claims, not vocabulary.** `check_explanation` verifies the one
  thing that can actually be false -- the named direction (clockwise vs
  counterclockwise) against the granted `rotation` -- and blocks position/layout
  claims (left/right, top/bottom, wedge/dash, etc.) that were never given to
  the model. Words like "rotation", "orientation", "spatial arrangement",
  "points away" are deliberately NOT checked: they are filler with no true/false
  content, and blocking them rejected correct answers four separate times.
  Ambiguous words (`top`, `bottom`, `right`) are phrase-gated because they also
  mean "highest-ranked"/"correct". Don't reintroduce a synonym blocklist.
- Ground every fact the LLM may state (priorities, reason, rotation). Anything
  ungrounded in the prompt is treated as fabrication.
- Diagnose LLM failures from the raw rejected text. The test loop prints
  `raw_response_that_failed` for every LLM rejection; use that, not a rerun.

## Testing

- OCSR benchmark: 29 molecules in the notebook (`test_molecules` 20 +
  `more_smiles` 9), ~80% exact match on clean images.
- Tutoring layer: `llm_test_cases_v2` (cell `llmtest_v2_cases`), 11 cases: 3
  error paths that must short-circuit without calling the LLM, plus 8 that reach
  it (single/multi-stereocenter scoping, an all-carbon tie-break, zwitterion,
  salt). Prints a `passed/reached` tally.
- Results vary run to run with unchanged code (6/8, 7/8 and 8/8 all seen)
  because qwen is non-deterministic. Judge reliability over several runs, not a
  single tally.

## Known limitations and open issues

- **Both-directions false positive: fixed in the backend only.**
  `backend/app/tutoring/checks.py` no longer rejects a response for naming
  both directions. It splits the text into clauses, pairs each direction with
  the nearest R/S label, and rejects only impossible pairings (S+clockwise,
  R+counterclockwise), or an unlabeled direction that differs from the granted
  one. The notebook's `check_explanation` still has the old rule. Known edge:
  a sulfur atom written as "S" near a direction word would be read as a label.
- **Tie-break reasoning is one level deep.** `build_priority_reason` only looks
  at the atoms attached to each group. Ties that need deeper CIP exploration
  (e.g. propyl vs ethyl) can yield a shallow or uninformative reason, which the
  LLM then restates faithfully. Untested beyond the 3-methylhexane case, whose
  explanation was accurate but vague.
- **Timeouts:** mitigated (timeout 100s), not root-caused. A timeout shows up as
  a silent fallback, indistinguishable in the printed tally from a rejected
  response unless the `error` key is checked.
- **E/Z:** DECIMER failed both test cases, and `validate_molecule` checks atoms
  only. Out of scope for the MVP.
- **Fischer projections:** pure flat-line Fischer is a confirmed DECIMER gap.
  D-glucose came back as C5H10O8 instead of C6H12O6 (missing carbon, gem-diol
  oxygens, a hallucinated tritium label, no stereocenters). DECIMER reportedly
  handles a Fischer-style layout when wedge/dash marks are drawn; that hybrid
  is untested. RDKit cannot help (it only draws, never reads, images) and
  converting flat lines to wedges needs the answer in advance. Future idea, not
  started: a dedicated parser (find the cross layout, OCR the four labels,
  apply the Fischer rule: vertical = away, horizontal = toward).
- **Hand-drawn/photographed images:** untested. All benchmarking used clean,
  computer-generated images.
- The Fischer test cell in the notebook reads an absolute path in Downloads;
  move that image into `notebooks/` and use a relative path.

## Backend cleanup still pending (user has seen these, not yet decided)

The pipeline now also lives in `backend/app/` (FastAPI). Two cleanups to
`validate_molecule` (`backend/app/chemistry/validation.py`), deliberately left
as-is until the user decides:

1. **Dict keys have spaces/capitals** (`"Atom index"`, `"Number of
   stereocenters"`). Typos only fail at runtime, the editor can't autocomplete
   or catch them, and the JSON would force the phone app to write
   `data["Atom index"]`. Fix: return a small typed object (dataclass) so it's
   `result.atom_index`.
2. **It accepts a string or a list and always returns a list**, so every
   caller must remember `[0]` (the grader does `validate_molecule(...)[0]`);
   forgetting it gives a confusing error elsewhere. Fix: take one SMILES,
   return one result, and let callers loop.

Neither is a bug today; both are cheapest to fix now, while only a few backend
modules call `validate_molecule`. The notebook keeps its own copy, so changing
the backend version doesn't break it.

## What to help with next, in likely priority order

1. Finish hardening the tutoring layer: fix the both-directions false positive,
   add deeper-tie-break cases, and run the test set several times to get a
   real pass rate.
2. Test the wedge/dash Fischer hybrid, then hand-drawn/photographed input.
3. Only after all of the above: Phase 2 (multi-file structure, pytest suite,
   FastAPI backend, React frontend), and later the optional mechanism checker.

## Working style

- Every function here was hardened by trying to break it (bad types, empty
  strings, malformed molecules, wrong atom indices), not just happy paths.
  Keep that standard.
- Ask for the user's approval before changing code. Diagnose and propose, then
  wait. An explicit request ("remove that check") is approval for that change.
- When diagnosing LLM results, use the user's saved output rather than running
  fresh Ollama calls, since a rerun of a non-deterministic model may not
  reproduce their failure.
