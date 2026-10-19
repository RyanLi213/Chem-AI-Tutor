# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An organic chemistry tutor for stereochemistry. A student photographs a molecule, the backend reads it into SMILES (DECIMER), RDKit finds the stereocenters and their R/S labels, the student's answer is graded against RDKit, and an LLM explains why.

**Non-negotiable design rule: the LLM never computes chemistry.** RDKit decides every answer. The LLM only rephrases facts that deterministic code has already computed and placed in its prompt, and its output is checked before a student sees it. Do not propose designs where an LLM derives or guesses a chemistry result.

## Commands

Windows, PowerShell. The venv (`.venv-decimer`, Python 3.12) lives at the repo root. All backend imports are rooted at `app.`, so **run everything from `backend/`**; importing as `backend.app...` breaks.

```powershell
# install backend dependencies into the venv (from repo root)
.\.venv-decimer\Scripts\python.exe -m pip install -r backend\requirements.txt

# run the API (from backend/); interactive docs at http://127.0.0.1:8000/docs
cd backend
..\.venv-decimer\Scripts\python.exe -m uvicorn app.main:app --reload

# quick check of the chemistry path without the server or the LLM (from backend/)
..\.venv-decimer\Scripts\python.exe -c "from app.pipeline import analyze_smiles; print(analyze_smiles('C[C@H](O)C(=O)O')['stereocenters'])"
```

- There is **no test suite, linter, or formatter configured** yet (no `backend/tests/`, pytest not installed). Verification so far has been ad-hoc scripts.
- `uvicorn` and `python-multipart` are listed unpinned in `backend/requirements.txt`; `app.main` cannot import without `python-multipart`. Pin them once installed.
- `/grade` calls a local Ollama server (`qwen3:1.7b`). Override with env vars `OLLAMA_URL`, `LLM_MODEL`, `LLM_TIMEOUT` (see `app/config.py`). Without Ollama, grading still works and the explanation falls back to plain text.
- Importing DECIMER loads TensorFlow and takes many seconds; it is imported lazily inside `ocsr/decimer_client.py` so chemistry-only code stays fast. The dev machine is CPU-only, so LLM calls can take 30-100s.

## Backend architecture (`backend/app/`)

`pipeline.py` is the only thing the API layer calls. Two flows:

- **`/analyze`** (image upload): `ocsr` (DECIMER, image to SMILES) -> `chemistry/validation.py` (canonicalize, find stereocenters) -> `chemistry/rendering.py` (SVG with stereocenters highlighted and numbered). Returns the canonical SMILES, stereocenter atom indices, undefined stereocenters, and the SVG.
- **`/grade`** (SMILES + atom index + answer): `grading/stereocenter.py` (compare to RDKit's label) -> `tutoring/safe_explanation.py` (LLM explanation, verified, with fallback).

Invariants that span files:

- **One atom numbering.** `validate_molecule` re-parses the canonical SMILES before indexing, and `draw_stereocenters_svg` does the same re-parse, so the number drawn on an atom is the index the grader expects. Clients must send back the canonical SMILES returned by `/analyze`. Changing canonicalization in one place and not the other reintroduces a bug where the same molecule gets different stereocenter indices.
- **Answers never go to the client before grading.** `/analyze` returns stereocenter indices only, and the SVG deliberately has no R/S annotation.
- **`validate_molecule(smiles)` takes one SMILES and returns a typed `MoleculeValidation`** (`.valid`, `.stereocenters`, `.undefined_stereocenters`, `.find_stereocenter(i)`); each `Stereocenter` has `.atom_index`, `.label`, `.priorities` (list of `Substituent`). It adds explicit Hs so all four substituents are ranked. An "undefined" stereocenter is a real one whose wedge/dash was not read; it is reported, never guessed.
- **The "why" is computed, then restated.** `chemistry/cip.py` produces the priority order (from RDKit's `_CIPNeighborOrder`), a reason sentence (`build_priority_reason(smiles, atom_index)`), and the rotation direction (`ROTATION_BY_LABEL`: R = clockwise, S = counterclockwise, by definition). `tutoring/prompts.py` puts those in the prompt using element names, not symbols, and asks for configurations written as `(R)`/`(S)`.
- **Tie-break reasons come from our own walk, refereed by RDKit.** RDKit exposes the ranking but not where a tie broke. When the top two groups start with the same element, `find_tie_break` walks both outward layer by layer (CIP counting: double bonds and ring closures add duplicate atoms; aromatic rings are kekulized first) and reports the first differing layer. It is a simplified CIP comparison, so `build_priority_reason` only uses it when its winner matches RDKit's order, and otherwise emits a generic sentence. `prepare_cip_mol` in `validation.py` is the single place atom numbering is set up; anything that indexes atoms must go through it.
- **Every LLM response is gated.** `get_safe_explanation` builds a plain fallback first, then returns the LLM text only if `tutoring/checks.py::check_explanation` passes; on a failed check, a timeout, or a grading error it returns the fallback.

### How `check_explanation` decides (read before editing it)

It checks claims, not vocabulary. An earlier blocklist of spatial words ("rotation", "orientation", "spatial arrangement") rejected correct explanations repeatedly and was removed; do not reintroduce one.

- Position/layout claims (left/right, on top, wedge/dash, toward) are always rejected, because that information is never given to the model. `top`/`bottom`/`right` are phrase-gated since the bare words also mean "highest-ranked"/"correct".
- Direction claims are checked per clause: each "clockwise"/"counterclockwise" is paired with the nearest R/S label and must match `ROTATION_BY_LABEL`. Naming both directions is fine if each is paired correctly. An unlabeled direction must equal the molecule's real direction.
- For molecules containing sulfur, `strict_labels=True`: only `(S)`/`(R)` or "S configuration" count as labels, because a bare "S" may be the atom.

## Known defects (verified by running the code)

- **Pseudoasymmetric centers break grading.** RDKit labels them lowercase `r`/`s` (e.g. `C[C@H](O)[C@H](O)[C@H](O)C`). The grader upper-cases the student's answer, so every answer is marked wrong, and `describe_rotation` raises `KeyError`, which `get_safe_explanation` does not catch (it only catches `requests` errors).
- **`check_explanation` gaps:** praise for a wrong answer (or the reverse) is not detected beyond the phrase "correct answer is X"; "R group" is read as the label R on non-sulfur molecules; the model's restated priority order is not verified.
- **Input limits:** E/Z is not supported (DECIMER failed both test cases; validation checks atoms only). Flat-line Fischer projections fail in DECIMER (D-glucose came back with the wrong formula). Hand-drawn and phone-photo input is untested. One molecule per image.

## Notebook (`notebooks/`)

`Untitled-1.ipynb` is the original research sandbox and holds **older copies** of the pipeline: its `validate_molecule` returns dicts with spaced keys and accepts lists, and its `check_explanation` predates the backend fixes. Code moved between notebook and backend needs converting. `notebooks/CLAUDE.md` has notebook-specific detail.

- The notebook is too large for the Read tool. Inspect it with the venv Python's `json` module; cells have stable ids.
- The user edits it live in VS Code. Edits written to the `.ipynb` on disk are not reliably picked up by the open editor or kernel, which has caused false "still broken" reports; have the user revert the file and re-run cells.

## Project context

- `README.md` holds the original plan and milestone list; its checkboxes lag behind reality (the backend exists; no frontend does). It names the Claude API and a React web frontend; current code uses local Ollama, and the intended client is a mobile app. `checkpoints.md` is the log of tested findings and limitations.
- Planned next: a "find the chiral centers" step (label atoms, grade the student's chosen set), batch grading of all centers in one request, a hosted LLM, then the mobile client.
- The user wants to approve code changes first: diagnose and propose, then wait. An explicit request to change something is the approval for that change. When diagnosing LLM output, use the user's saved results; a fresh call to a non-deterministic model may not reproduce their failure.
