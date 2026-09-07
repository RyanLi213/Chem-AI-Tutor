# Organic Chemistry Structure Tutor Project Framework

## Goal

Build a study tool that helps students learn and understand organic chemistry structures. Starting with stereochemistry (R/S, E/Z), this tool helps students parse molecules that they provide (hand-drawn or not) and the tool outputs  a validated digital representation. Using deterministic chemistry rules (no LLM calculations), the tool checks for correctness and only uses LLM for explaination and tutoring language. The differentiator vs existing "AI Chemistry Solver" apps is that every answer is backed by a verifiable chemistry engine and the tool teaches students by making them do the reasoning, not just handingg them the answers.

## Architecture

1. **Input capture:** student uploads a photo of the structure, hand-drawn or not
2. **Vision parsing (OSCR):** converts the image into a machine-readable format (SMILES). Uses an existing open-source model (DECIMER) rather than building a vision model from scratch
3. **Chemistry validation layer (RDKit):** parses the SMILES string(s), checks the valence and charge validity, and assigns the real CIP stereochemistry labels (R/S, E/Z) using RDKit's `rdCIPLabeler`. This is deterministic "definite truth" layer, no LLM involved
4. **Grading/comparison engine:** compares validated structure (or student's stereochemistry assignment) against the correct answer, and pinpoints exactly what's wrong (e.g. "assigned R, correct is S because the OH group at C2 outranks the ethyl group")
5. **Tutoring layer (LLM):** takes the validated structured data from layers 3 and 4 and turns it into a natural language explanation. It only explains what the layers 3/4 already determined

## Tech Stack
- **Backend / core engine:** Python, FastAPI or Flask for API layer
- **LLM tutoring:** Claude API, called only after the deterministic layers have produced validated results
- **Frontend:** JavaScript/React, with browser-based editor (Kekule.js or JSME) so students can draw structures directly instead of only uploading photos
- **Validation/testing:** build a small test set of structures with known correct R/S answers (from textbook problem sets) to regression-test the RDKit pipeline as it is built

## Project Build Order
This project is built in two phases: prove the chemistry/AI logic actually works correctly in a research notebook, then rebuild it as real software. 

### Phase 1 — Research & validation (notebook)
 
All prototyping, testing, and stress-testing happens in a single Jupyter notebook. The priority here is correctness and understanding failure modes, not code organization — this is where every entry in the [Known limitations](#known-limitations) table below came from.
 
- [x] **Milestone 0 — Environment setup.** Python, RDKit, and DECIMER installed and verified locally.
- [x] **Milestone 1 — OCSR pipeline.** Image → SMILES proven working, benchmarked against a 29-molecule verified test set (~80% exact-match accuracy).
- [x] **Milestone 2 — RDKit validation layer.** `validate_molecule()` built and stress-tested against 0/1/2/3-stereocenter molecules, invalid input, wrong data types, non-carbon stereocenters, and charged species.
- [ ] **Milestone 3 (MVP) — Stereochemistry quiz grading.** Core grading (`grade_stereocenter_answer()`) built and stress-tested. Currently fixing an atom-indexing fragility issue before considering this done.
- [ ] **Milestone 4 — Mechanism step-checker.** Not started; revisit after Milestone 3 is solid.
- [ ] **Milestone 5 — LLM tutoring layer (prototype).** Not built yet. Design confirmed: feed the LLM the deterministic result and constrain it to explaining, not computing.
**Phase 1 is done** once Milestones 0–5 are proven correct and stress-tested in the notebook. Phase 2 does not start before that.
 
### Phase 2 — Production framework (post-notebook)
 
Once the logic is proven, rebuild it as real, industry-structured software — not a research notebook. Modeled on how a production engineering team would actually structure this: separated concerns, a real test suite, a real backend API, and a real frontend.
 
- [ ] **Milestone 6 — Repo scaffolding.** Proper package layout (`src/`, `tests/`, `api/`, `frontend/`), dependency management (`pyproject.toml`), CI config.
- [ ] **Milestone 7 — Modularize the logic.** Refactor the notebook's functions into clean, documented, importable modules with a single responsibility each — e.g. `ocsr/` (DECIMER wrapper), `validation/` (RDKit engine, `validate_molecule`), `grading/` (`grade_stereocenter_answer` and friends), `tutoring/` (LLM prompt layer).
- [ ] **Milestone 8 — Real test suite.** Migrate the 29-molecule verified set (and the stress-test cases) from notebook `print()` statements into `pytest` unit tests and fixtures — runnable in CI, not just eyeballed in a notebook.
- [ ] **Milestone 9 — Backend API.** FastAPI service wrapping the validated engine (`/ocsr`, `/validate`, `/grade` endpoints), with request/response schemas, structured error handling, and logging.
- [ ] **Milestone 10 — Frontend.** React app calling the backend API, with a browser-based structure-drawing editor (Kekule.js or JSME) and a quiz UI.
- [ ] **Milestone 11 — Deployment.** Containerization, CI/CD, environment and config management.

## Learning Checkpoints (tied to milestones)
 
- Before Milestone 2: learn CIP priority rules (how to rank substituents) well enough to manually verify RDKit's output on 10–15 test molecules.
- Before Milestone 3: work through a stereochemistry problem set (R/S assignment) from an intro orgo course, using own answers as a validation set for the grading engine.
- Before Milestone 4: learn basic mechanism types (SN1/SN2, E1/E2, addition/elimination) — only needed once past the stereochemistry MVP.
