# Project context for Claude Code

This file is read automatically by Claude Code. It exists so a fresh session
has full context on this project without the user re-explaining it.

## What this project is

An organic chemistry study tool that helps students master stereochemistry
(R/S, and eventually E/Z) by parsing a photo or drawing of a molecule into a
validated digital representation, grading correctness with deterministic
chemistry rules, and using an LLM only to explain results in plain language.

**The core design principle, non-negotiable:** an LLM never computes
chemistry. RDKit (deterministic, rule-based) always decides what's correct.
The LLM only explains a result that's already been computed. Do not suggest
architectures that let an LLM guess or compute a chemistry answer directly.

## Current phase

This project is intentionally in **Phase 1: research & validation**, built
in a single Jupyter notebook, not a production codebase yet. Code quality
bar right now is "correct and well-tested," not "production-structured."
**Do not** suggest migrating to a multi-file package structure yet -- that's
explicitly Phase 2, sequenced after Phase 1's logic is fully proven. See
`README.md` in this repo for the full phase breakdown and milestone list.

## Environment

- Python 3.10 or 3.11, in a venv (RDKit + DECIMER's TensorFlow dependency
  need this range; newer Python versions may lack wheels for these).
- Installed: `rdkit`, `decimer`.
- Local LLM: Ollama running `qwen3:1.7b` (chosen for the dev machine's
  modest CPU-only hardware -- a ThinkPad L13, Core i5, no dedicated GPU).
  Ollama exposes a local API at `http://localhost:11434/api/generate`.
- Production LLM plan (not yet built): a cheap hosted open-source model API
  (e.g. Groq) rather than trying to run inference on-device in a mobile app --
  on-device inference was evaluated and rejected as too slow/heavy for a
  responsive quiz app.

## Architecture (5 layers)

1. **Input capture** -- photo upload or in-app structure editor (not built yet).
2. **Vision parsing (OCSR)** -- DECIMER, image to SMILES. Built and benchmarked.
3. **Chemistry validation (RDKit)** -- deterministic ground truth. Built and hardened.
4. **Grading** -- compares a student's answer to RDKit's answer. Built and hardened.
5. **LLM tutoring layer** -- explains a graded result in plain language. In progress.

## Key functions that already exist (current, verified versions)

### `validate_molecule(smiles)` -- the core deterministic validation engine

Accepts a single SMILES string or a list of them. Returns a list of result
dicts, one per input, always with the same four keys regardless of validity
(this consistency was a real bug fixed during development -- do not remove
any key from any return path).

```python
def validate_molecule(smile_string: str):
    if isinstance(smile_string, str):
        smile_string = [smile_string]

    results = []

    for smi in smile_string:
        if not smi or not smi.strip():
            results.append({
                "Valid": False,
                "Number of stereocenters": 0,
                "Stereocenters": [],
                "Undefined stereocenters": []
            })
            continue

        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            results.append({
                "Valid": False,
                "Number of stereocenters": 0,
                "Stereocenters": [],
                "Undefined stereocenters": []
            })
            continue

        # Canonicalize before indexing -- fixes a real bug where the same
        # molecule written in a different atom order put its stereocenter
        # at a different index. Do not remove this step.
        canon_smiles = Chem.MolToSmiles(mol)
        mol = Chem.MolFromSmiles(canon_smiles)

        rdCIPLabeler.AssignCIPLabels(mol)

        stereocenters = []
        for atom in mol.GetAtoms():
            if atom.HasProp("_CIPCode"):
                stereocenters.append({
                    "Atom index": atom.GetIdx(),
                    "label": atom.GetProp("_CIPCode")
                })

        # Separately detect stereocenters that exist but have no wedge/dash
        # specified -- without this, "no stereocenter" and "unspecified
        # stereocenter" looked identical, which is a real, meaningful bug
        # for a tool grading student-drawn structures.
        all_centers = FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False)
        undefined_stereocenters = [idx for idx, label in all_centers if label == "?"]

        results.append({
            "Valid": True,
            "Number of stereocenters": len(stereocenters),
            "Stereocenters": stereocenters,
            "Undefined stereocenters": undefined_stereocenters
        })

    return results
```

Verified via a 10-case self-checking test suite (valid/invalid SMILES, empty
string, undefined stereochemistry, a fake stereocenter with duplicate
substituents, a salt/multi-component SMILES, a partially-defined molecule,
and a combined R/S + E/Z molecule). All 10 pass. Known remaining gap: does
not check bond stereochemistry (E/Z), only atoms -- see Known Limitations.

### `grade_stereocenter_answer(correct_smiles, atom_index, student_answer)`

```python
def grade_stereocenter_answer(correct_smiles: str, atom_index: int, student_answer):
    if not isinstance(student_answer, str):
        return {"error": f"Answer must be a string, got {type(student_answer).__name__}"}

    cleaned_answer = student_answer.strip().upper()

    result = validate_molecule(correct_smiles)
    stereocenters = result[0]["Stereocenters"]

    correct_label = None
    for center in stereocenters:
        if center["Atom index"] == atom_index:
            correct_label = center["label"]

    if correct_label is None:
        return {"error": f"No stereocenter found at atom index {atom_index}"}

    is_correct = (cleaned_answer == correct_label)
    return {
        "correct_label": correct_label,
        "student_answer": cleaned_answer,
        "is_correct": is_correct
    }
```

Stress-tested against: multi-stereocenter molecules, empty string answers,
nonsense text answers, invalid molecule SMILES, and wrong data types
(e.g. an int instead of a string). All handled without crashing.

### OCSR pipeline -- `validate_DECIMER_pipeline(smile_string)`

Combines image generation (RDKit), OCSR (DECIMER), and validation
(`validate_molecule`) into one round-trip test. Accepts a string or list.

```python
def validate_DECIMER_pipeline(smile_string):
    if isinstance(smile_string, str):
        smile_string = [smile_string]

    results = []
    for smi in smile_string:
        mol = Chem.MolFromSmiles(smi)
        temp_img_path = "temp_molecule.png"
        Draw.MolToFile(mol, temp_img_path, size=(400, 400), wedgeBonds=True)

        predicted_smiles = predict_SMILES(temp_img_path)

        original_validation = validate_molecule(smi)
        predicted_validation = validate_molecule(predicted_smiles)
        canonical_match = Chem.CanonSmiles(smi) == Chem.CanonSmiles(predicted_smiles)

        results.append({
            "Original SMILE string": smi,
            "Predicted SMILE string": predicted_smiles,
            "Canonical match": canonical_match,
            "Original validation": original_validation,
            "Predicted validation": predicted_validation
        })

    return results
```

Benchmarked against a 29-molecule verified test set (see
`decimer_test_set_20.py` in this repo for 20 of them) at ~80% exact-match
accuracy, in line with DECIMER's own published benchmarks. R/S stereocenters
are reliable; E/Z double bonds are not (DECIMER failed both E/Z test cases).

### `calculate_accuracy(results)`

```python
def calculate_accuracy(results):
    total = len(results)
    correct = sum(1 for r in results if r["Canonical match"])
    accuracy = (correct / total) * 100
    return f"{correct}/{total} correct ({accuracy:.1f}%)"
```

### LLM explanation layer (in progress, not yet fully wired up)

```python
def build_explanation_prompt(grading_result: dict, smiles: str) -> str:
    return f"""### Role
You are a friendly, encouraging organic chemistry tutor helping a student learn stereochemistry.

### Context
- Molecule (SMILES): {smiles}
- Student's answer: {grading_result['student_answer']}
- Correct answer: {grading_result['correct_label']}
- Was the student correct?: {grading_result['is_correct']}

### Task
Write a short explanation (2-3 sentences) telling the student whether they got it right or wrong.

### Rules (important)
- Only use the facts listed in Context above. Do NOT invent, guess, or compute any new chemistry.
- If correct: briefly confirm it and give quick encouragement.
- If incorrect: clearly state the correct answer -- never just say "wrong" without including it.
- Keep the tone encouraging, never harsh.

### Output format
Return ONLY the explanation text. No headers, no bullet points, no restating these instructions.
"""

def get_explanation(prompt: str) -> str:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "qwen3:1.7b", "prompt": prompt, "stream": False}
    )
    return response.json()["response"]
```

Not yet stress-tested. Next work here: confirm Ollama is actually running
on the dev machine (install was in progress, hit a PATH issue on Windows --
`ollama` command not recognized after install, likely needs the Ollama app
launched once from the Start menu to finish registering itself), then test
`get_explanation` end to end with real graded results.

## Known limitations (do not silently "fix" these without flagging it to the user -- some are intentionally out of scope for now)

- **E/Z (double bond) stereochemistry**: unreliable in DECIMER, and
  `validate_molecule` doesn't check bonds at all yet, only atoms. Out of
  scope for the MVP on purpose.
- **Fischer projections**: unconfirmed whether DECIMER supports this
  drawing convention at all. Untested, high-priority open question given
  how central Fischer projections are to teaching stereochemistry.
- **Hand-drawn/photographed images**: untested. All benchmarking so far
  used clean, computer-generated images (the easy case).
- **Atom-index fragility and undefined-stereochemistry detection**: both
  were real bugs, both are now fixed (see `validate_molecule` above) and
  verified with a 10-case test suite.

## What to help with next, in likely priority order

1. Get Ollama running reliably on the dev machine, then finish wiring up
   and stress-testing the LLM explanation layer (empty/error grading
   results, very long or unusual SMILES, correct vs. incorrect answers).
2. Extend `grade_stereocenter_answer` and the prompt to eventually explain
   *why* an answer is R or S (CIP substituent priority ranking), not just
   state the answer -- RDKit's CIP labeler gives the final label but not an
   easy human-readable priority ranking, so this needs real investigation,
   not just an assumption that the data is already available.
3. Test Fischer projection support and hand-drawn image accuracy (both
   currently unknown, both matter a lot for real-world use).
4. Only after all of the above is solid: begin Phase 2 (see `README.md`)
   -- migrating to a real multi-file project structure, a pytest suite, a
   FastAPI backend, and a React frontend.

## Working style note

This project has been built through deliberate, incremental stress-testing
-- every function here was hardened by actively trying to break it (bad
input types, empty strings, malformed molecules, wrong atom indices) before
being trusted, not just tested on the happy path. Keep that standard when
extending it.
